import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# FastAPI app configuration#

app = FastAPI()

#templates/ folder for HTML templates -- this will be for our landing pages
templates = Jinja2Templates(directory="templates")

#static/ folder for css, js, and images
app.mount("/static", StaticFiles(directory="static"), name ="static")

#local memory cart - resets when app is restarted fully

local_cart =[]

def search_bestbuy_mock(query: str):
    return [
        {
            "title": f"{query} (Best Buy Edition)",
            "platform": "PS5",
            "price": 59.99,
            "retailer": "Best Buy",
            "product_url": "https://www.bestbuy.com/site/example",
            "thumbnail_url": "https://via.placeholder.com/150",
            "sku": "BB123"
        }
    ]


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
async def home(request: Request):
    # Just show login as the "home" page
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...)
):

    # Redirect to profile page after "login".
    response = RedirectResponse(url="/profile", status_code=303)
    return response


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


@app.get("/search", response_class=HTMLResponse)
async def search_games_page(request: Request, q: str | None = None):
    results = []
    if q:
        # Combine results from different retailers -- filler data for now API data to go in here
        bb_results = search_bestbuy_mock(q)
        tg_results = search_target_mock(q)
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