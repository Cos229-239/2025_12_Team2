from ast import Store
from asyncio.windows_events import NULL
import os
from argon2 import PasswordHasher # used for hashing password for protection
from argon2 import exceptions # used for incorrect password or username entry
from typing import Annotated, Optional # used for username and password inputs
from fastapi import FastAPI, Query, Request, Form, status
from fastapi.background import P
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx # for api call
from urllib.parse import quote
import asyncio
from typing import Optional

class pasCatch: # used for user account checking
    def __init__(self, name, password):
        self.name = name
        self.password = password

hasher = PasswordHasher() # Instantiation needed for hasher to work, cannot just use PasswordHasher

user_list = [] # Python list of user accounts

def update_user_list():
    with open("db/userAccounts.txt", "r") as file:
        for line in file:
            temp_list = line.split() # Split each line into temp list
            user_list.append(pasCatch(temp_list[0], temp_list[1]))

# FastAPI app configuration#

app = FastAPI()

#templates/ folder for HTML templates -- this will be for our landing pages
templates = Jinja2Templates(directory="templates")

#static/ folder for css, js, and images
app.mount("/static", StaticFiles(directory="static"), name ="static")

#local memory cart - resets when app is restarted fully

local_cart =[]

# real API call to best buy, needed dependency libary is httpx

BESTBUY_API_KEY = os.getenv("BESTBUY_API_KEY")
print("BESTBUY_API_KEY present:", bool(BESTBUY_API_KEY)) # checking if the api key was working, can remove later

async def search_bestbuy(query: str, page_size: int = 100):
    api_key = os.getenv("BESTBUY_API_KEY")
    if not api_key:
        print("BB: missing api key")
        return[]

    q = quote(query)
    tokens = [t for t in query.split() if t]

    category_id = "pcmcat1497456762821" #digital gaming best buy category
    search_filter = "&".join([f"search={quote(t)}" for t in tokens]) if tokens else "search=*"
    criteria = f"((categoryPath.id={category_id})&({search_filter}))" #includes regular search filter and category id to force digital gaming search

    url = f"https://api.bestbuy.com/v1/products{criteria}"

    params = {
        "apiKey": BESTBUY_API_KEY,
        "format": "json",
        "show": "sku,name,salePrice,regularPrice,url,image,thumbnailImage,addToCartUrl,platform",
        "pageSize": min(max(page_size, 1), 100),
        "sort": "salePrice.asc",
    }

    timeout = httpx.Timeout(10.0, connect=5.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, params=params)
        print("BB request:", resp.request.url) # debug
        print("BB status:", resp.status_code) # debug
        resp.raise_for_status()
        data = resp.json()

    products = data.get("products", []) or []
    print("BB total:", data.get("total"), "returned:", len(products))#debug

    results = []
    for p in products:
        platform_value = p.get("platform")

        if not platform_value:
            name = (p.get("name") or "").lower()
            if "pc" in name:
                platform_value = "PC"
            elif "xbox" in name:
                platform_value = "Xbox"
            elif "playstation" in name or "ps5" in name or "ps4" in name:
                platform_value = "PlayStation"
            elif "nintendo switch" in name or "switch" in name:
                platform_value = "Nintento Switch"
            else:
                platform_value = "-"


        results.append(
            {
                "title": p.get("name") or "Unknown",
                "price": p.get("salePrice"),
                "sku": str(p.get("sku") or ""),
                "retailer": "Best Buy",
                "platform":platform_value,
                "product_url": p.get("url") or "",
                "thumbnail_url": p.get("thumbnailImage") or p.get("image") or "",
            }
        )

    return results


async def search_steam(query: str, page_size: int = 100, cc:str = "us", lang: str = "english"):
    term = query.strip()
    if not term:
        return[]

    count = min(max(page_size,1),25)

    url = "https://store.steampowered.com/api/storesearch/"
    params = {
        "term":term,
        "l": lang,
        "cc": cc,
        "page": 1,
        "count":count,
    }

    timeout = httpx.Timeout(30.0, connect = 15.0)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            resp = await client.get(url, params = params)
            print("Steam request:", resp.request.url) #debug
            print ("Steam status:", resp.status_code) #debug
            resp.raise_for_status()
            data = resp.json()
    except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
        print("Steam timeout:", repr(e))
        return []
    except httpx.HTTPError as e:
        print("Steam HTTP error:", repr(e))
        return []

    items = data.get("items", []) or []

    results = []
    for it in items:
        appid= it.get("id")
        title= it.get("name") or "Unknown"
        store_url = f"https://store.steampowered.com/app/{appid}/" if appid else ""

        price = None
        price_obj = it.get("price")
        if isinstance(price_obj, dict):
            final_cents = price_obj.get("final")
            if isinstance(final_cents, int):
                price = final_cents / 100.0


        thumb= it.get("tiny_image") or ""

        results.append(
            {
                "title": title,
                "price": price,
                "sku": str(appid or ""),
                "retailer": "Steam",
                "platform":"PC",
                "product_url": store_url,
                "thumbnail_url": thumb,
                }          
        )
    return results

async def search_bestbuy_and_steam(query: str, page_size_bestbuy: int = 25, page_size_steam: int = 25):
    bb_task = search_bestbuy(query=query, page_size=page_size_bestbuy)
    steam_task = search_steam(query=query,page_size=page_size_steam)

    bb_results, steam_results = await asyncio.gather(bb_task, steam_task, return_exceptions=True)

    if isinstance(bb_results,Exception):
        print("Best buy search failed:", repr(bb_results))
        bb_results = []

    if isinstance(steam_results,Exception):
        print("Steam search failed:", repr(steam_results))
        steam_results = []


    combined = (bb_results or []) + (steam_results or [])
    combined.sort(key=lambda x: (x["price"] is None, x["price"] if x["price"] is not None else 0))

    return combined





# --- Routes / pages ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, error: str = None):
    # Just show login as the "home" page
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


update_user_list()

@app.post("/login")
async def login(
    # The setup below allows for username and password to be blank
    username: Optional[str] = Form(None), 
    password: Optional[str] = Form(None)
    ):
    # Checks input username and password against existing list
    try:
        # Successful Login
        for obj in user_list:
            if obj.name == username and hasher.verify(obj.password, password):
                return RedirectResponse(url="/profile", status_code=303)
    except exceptions.VerifyMismatchError:
        # Unsuccessful Login
        error_message = "Invalid username or password!"
        return RedirectResponse(url=f"/?error={error_message}", status_code=status.HTTP_303_SEE_OTHER)
    if username == None or password == None:
        # Login pressed with no username/password
        error_message = "Please enter username and password!"
        return RedirectResponse(url=f"/?error={error_message}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/creation", response_class=HTMLResponse)
async def creation(request: Request, error: str = None):
    return templates.TemplateResponse("creation.html", {"request": request, "error": error})


@app.post("/creation")
async def createProfile(
    request: Request,
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    confirm_password:  Optional[str] = Form(None)
    ):
    error_message = None
    alreadyExists = False
    for obj in user_list:
        if obj.name == username: # checks against hashed list
            # User already exists
            alreadyExists = True

    if alreadyExists:
        # Username taken, refresh page with error message
        error_message = "Username taken!"
        result = templates.TemplateResponse("creation.html", {"request": request, "error1": error_message})
    elif confirm_password != password or password == "":
        # Passwords don't match, refresh page with error message
        error_message = "Passwords do not match!"
        result = templates.TemplateResponse("creation.html", {"request": request, "error2": error_message})
    elif username == None or (password == None and confirm_password == None):
        # Login pressed with no username/password
        error_message = "Please enter username and password!"
        result = templates.TemplateResponse("creation.html", {"request": request, "error2": error_message})
    else:
        hashedPassword = hasher.hash(password) # hashes password with Argon2 PasswordHasher
        result = RedirectResponse(url="/profile", status_code=303)
        # Write new username and password to userAccounts file
        with open("db/userAccounts.txt", "a") as file:
            file.write("\n" + username + " " + hashedPassword)
        update_user_list() # Update system list with new user
    
    # Redirect to profile page after "login".
    return result


@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    # Dummy profile data
    user_profile = {
        "username": "demo_user",
        "display_name": "Demo User",
        "favorite_platform": "PC"
    }
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "profile": user_profile
        }
    )

# Attempt at friend HTML page.
@app.get("/friends", response_class=HTMLResponse)
async def friends(request: Request):
    return templates.TemplateResponse("friends.html", {"request": request})
    # Dummy friends profile data
   


@app.get("/search", response_class=HTMLResponse)
async def search_games_page(request: Request, q: str | None = None):
    results = []

    if q:
       results = await search_bestbuy_and_steam(q, page_size_bestbuy=25, page_size_steam=25)

    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "query": q or "",
            "results": results
        }
    )


@app.post("/cart/add")
async def add_to_cart(
    retailer: str = Form(...),
    title: str = Form(...),
    sku: str = Form(...),
    price: Optional[float] = Form(None), # update to optional to solve for steam no string/free values from crashing when adding cart. 
    product_url: str = Form(...)
):
    # Add item to in-memory cart
    local_cart.append(
        {
            "retailer": retailer,
            "title": title,
            "sku": sku,
            "price": price,
            "product_url": product_url
        }
    )
    # Redirect to cart page
    return RedirectResponse(url="/cart", status_code=303)


@app.get("/cart", response_class=HTMLResponse)
async def view_cart(request: Request):
    return templates.TemplateResponse(
        "cart.html",
        {
            "request": request,
            "items": local_cart
        }
    )

@app.get("/purchase", response_class=HTMLResponse)
async def view_purchase(request: Request):
    total = sum(float(item.get("price", 0) or 0) for item in local_cart)
    print("TOTAL =", total)
    return templates.TemplateResponse(
        "purchase.html",
        {
            "request": request,
            "items": local_cart,
            "total": total
        }
    )

