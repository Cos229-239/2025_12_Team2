from asyncio.windows_events import NULL
import os
from argon2 import PasswordHasher # used for hashing password for protection
from argon2 import exceptions # used for incorrect password or username entry
from typing import Annotated, Optional # used for username and password inputs
from fastapi import FastAPI, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx # for api call
from urllib.parse import quote

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

async def search_bestbuy(query: str, page_size: int = 50):
    api_key = os.getenv("BESTBUY_API_KEY")
    if not api_key:
        print("BB: missing api key")
        return[]

    q = quote(query)
    tokens = [t for t in query.split() if t]
                 # working filter for category search --- cat000000 might just be best buy products only? "sold by best buy"
    #criteria = "(categoryPath.id=cat00000&(" + "&".join([f"search={quote(t)}" for t in tokens]) + "))"

                #original multi word searching
    criteria = "(" + "&".join([f"search={quote(t)}" for t in tokens]) + ")"
    

                # not functional -- pcmat found 
    #criteria = "(categoryPath.id=pcmcat1497456762821(" + "&".join([f"search={quote(t)}" for t in tokens]) + "))"
    #pcmcat1497456762821
    #criteria = "(subCategories.id=pcmcat1497456762821(" + "&".join([f"search={quote(t)}" for t in tokens]) + "))"

    url = f"https://api.bestbuy.com/v1/products{criteria}"

    params = {
        "apiKey": BESTBUY_API_KEY,
        "format": "json",
        # "category": "*video game",
        "show": "sku,name,salePrice,regularPrice,url,image,thumbnailImage,addToCartUrl",
        "pageSize": min(max(page_size, 1), 25),
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
        results.append(
            {
                "title": p.get("name") or "Unknown",
                "price": p.get("salePrice"),
                "sku": str(p.get("sku") or ""),
                "retailer": "Best Buy",
                "product_url": p.get("url") or "",
                "thumbnail_url": p.get("thumbnailImage") or p.get("image") or "",
            }
        )

    return results


#MOCK SEARCH
# def search_bestbuy_mock(query: str):
#     return [
#         {
#             "title": f"{query} (Best Buy Edition)",
#             "platform": "PS5",
#             "price": 59.99,
#             "retailer": "Best Buy",
#             "product_url": "https://www.bestbuy.com/site/example",
#             "thumbnail_url": "https://via.placeholder.com/150",
#             "sku": "BB123"
#         }
#     ]




#mock dummy target api
def search_target_mock(query: str):
    return [
        {
            "title": f"{query} (Target Version)",
            "platform": "Xbox",
            "price": 54.99,
            "retailer": "Target",
            "product_url": "https://www.target.com/p/example",
            "thumbnail_url": "https://via.placeholder.com/150",
            "sku": "TG123"
        }
    ]


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
    # if q:
    #     # Combine results from different retailers -- filler data for now API data to go in here
    #     # bb_results = await search_bestbuy(q)
    #             # mock results
    #     bb_results = search_bestbuy_mock(q)
    #     tg_results = search_target_mock(q)
    #     results = bb_results + tg_results


    ##DEBUGGING
    if q:
        bb_results = await search_bestbuy(q)
        print("BB results:", len(bb_results))
        tg_results = search_target_mock(q)
        print("Target results:", len(tg_results))
        results = bb_results + tg_results


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
    price: float = Form(...),
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