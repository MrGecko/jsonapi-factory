from flask import render_template, request, url_for

from app import app_bp, api_bp


@app_bp.route("/")
def index():
    return render_template("main/index.html")


@app_bp.route("/documentation")
def documentation():
    return render_template("docs/docs.html")

