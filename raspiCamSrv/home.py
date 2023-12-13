from flask import current_app, Blueprint, Response, flash, g, redirect, render_template, request, url_for
from werkzeug.exceptions import abort
from raspiCamSrv.auth import login_required
from raspiCamSrv.camera_pi import Camera
import datetime
import time
import logging

bp = Blueprint("home", __name__)

logger = logging.getLogger(__name__)

@bp.route("/")
@login_required
def index():
    return render_template("home/index.html")

def gen(camera):
    """Video streaming generator function."""
    logger.debug("In gen")
    yield b'--frame\r\n'
    while True:
        frame = camera.get_frame()
        l = len(frame)
        logger.debug("Got frame of length %s", l)
        yield b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n--frame\r\n'

@bp.route("/video_feed")
@login_required
def video_feed():
    logger.debug("In video_feed")
    return Response(gen(Camera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
    
@bp.route("/take_image", methods=("GET", "POST"))
@login_required
def take_image():
    logger.debug("In take_image")
    if request.method == "POST":
        path = current_app.instance_path
        filename = request.form["filename"]
        logger.debug("Filename from form is %s")
        if len(filename) == 0:
            timeImg = datetime.datetime.now()
            filename = "image_" + timeImg.strftime("%Y%m%d_%H%M%S") + ".jpeg"
        fp = path + "/" + filename
        Camera().takeImage(fp)
        return render_template("home/index.html")        
    