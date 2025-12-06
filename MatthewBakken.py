from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# FastAPI app configuration

app = FastAPI()

#templates/ folder for HTML templates -- this will be for our landing pages
templates = Jinja2Templates(directory="templates")

#static/ folder for css, js, and images
app.mount("static", StaticFiles(directory="static"), name ="static")

#local memory cart - resets when app is restarted fully

local_cart =[]