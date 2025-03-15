from flask import Blueprint, Response, flash, g, render_template, request, current_app
from werkzeug.exceptions import abort
from raspiCamSrv.camCfg import CameraCfg, CameraControls, CameraProperties, CameraConfig, ServerConfig, TriggerConfig, TuningConfig, vButton
from raspiCamSrv.camera_pi import Camera, CameraEvent
from raspiCamSrv.version import version
from raspiCamSrv.db import get_db
import os
from pathlib import Path
import json
from raspiCamSrv.auth import login_required
import logging

# Try to import flask_jwt_extended to avoid errors when upgrading to V2.11 from earlier versions
try:
    from flask_jwt_extended import create_access_token
except ImportError:
    pass


bp = Blueprint("settings", __name__)

logger = logging.getLogger(__name__)

@bp.route("/settings")
@login_required
def main():
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los)

@bp.route("/serverconfig", methods=("GET", "POST"))
@login_required
def serverconfig():
    logger.debug("serverconfig")
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    sc.lastSettingsTab = "settingsparams"
    if request.method == "POST":
        msg = None
        if sc.isTriggerRecording:
            msg = "Please go to 'Trigger' and stop the active process before changing the configuration"
        if not msg:
            photoType = request.form["phototype"]
            sc.photoType = photoType
            rawPhotoType = request.form["rawphototype"]
            sc.rawPhotoType = rawPhotoType
            videoType = request.form["videotype"]
            sc.videoType = videoType
            activeCam = int(request.form["activecamera"])
            # If active camera has changed reset stream size to force adaptation of sensor mode
            if activeCam != sc.activeCamera:
                cfg.liveViewConfig.stream_size = None
                cfg.photoConfig.stream_size = None
                cfg.rawConfig.stream_size = None
                cfg.videoConfig.stream_size = None
                sc.activeCamera = activeCam
                for cm in cs:
                    if activeCam == cm.num:
                        sc.activeCameraInfo = "Camera " + str(cm.num) + " (" + cm.model + ")"
                        sc.activeCameraModel = cm.model
                        break
                strCfg = cfg.streamingCfg
                newCamStr = str(activeCam)
                if newCamStr in strCfg:
                    ncfg = strCfg[newCamStr]
                    if "tuningconfig" in ncfg:
                        cfg.tuningConfig = ncfg["tuningconfig"]
                    else:
                        cfg.tuningConfig = TuningConfig
                else:
                    cfg.tuningConfig = TuningConfig
                Camera.switchCamera()
                msg = "Camera switched to " + sc.activeCameraInfo
                logger.debug("serverconfig - active camera set to %s", sc.activeCamera)
            recordAudio = not request.form.get("recordaudio") is None
            sc.recordAudio = recordAudio        
            audioSync = request.form["audiosync"]
            sc.audioSync = audioSync
            useHist = not request.form.get("showhistograms") is None
            if not useHist:
                sc.displayContent = "meta"
            sc.useHistograms = useHist
            sc.requireAuthForStreaming = not request.form.get("requireAuthForStreaming") is None
            useAPI = not request.form.get("useapi") is None
            sc.useAPI = useAPI
            sc.locLatitude = float(request.form["loclatitude"])
            sc.locLongitude = float(request.form["loclongitude"])
            sc.locElevation = float(request.form["locelevation"])
            sc.locTzKey = request.form["loctzkey"]
        if msg:
            flash(msg)
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los)

@bp.route("/resetServer", methods=("GET", "POST"))
@login_required
def resetServer():
    logger.debug("resetServer")
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    sc.lastSettingsTab = "settingsconfig"
    if request.method == "POST":
        logger.debug("Stopping camera system")
        Camera().stopCameraSystem()
        Camera.liveViewDeactivated = False
        Camera.thread = None
        Camera.thread2 = None
        Camera.videoThread = None
        Camera.photoSeriesThread = None
        logger.debug("Resetting server configuration")
        photoRoot = sc.photoRoot
        cfg = CameraCfg()
        cfg.cameras = []
        cfg.sensorModes = []
        cfg.rawFormats = []
        cfg.tuningConfig = TuningConfig()
        cfg.controls = CameraControls()
        cfg.controlsBackup = None
        cfg.cameraProperties = CameraProperties()
        cfg.liveViewConfig = CameraConfig()
        cfg.liveViewConfig.id = "LIVE"
        cfg.liveViewConfig.use_case = "Live view"
        cfg.liveViewConfig.stream = "lores"
        cfg.liveViewConfig.buffer_count = 6
        cfg.liveViewConfig.encode = "main"
        cfg.liveViewConfig.controls["FrameDurationLimits"] = (33333, 33333)
        cfg.photoConfig = CameraConfig()
        cfg.photoConfig.id = "FOTO"
        cfg.photoConfig.use_case = "Photo"
        cfg.photoConfig.buffer_count = 1
        cfg.photoConfig.controls["FrameDurationLimits"] = (100, 1000000000)
        cfg.rawConfig = CameraConfig()
        cfg.rawConfig.id = "PRAW"
        cfg.rawConfig.use_case = "Raw Photo"
        cfg.rawConfig.buffer_count = 1
        cfg.rawConfig.stream = "raw"
        cfg.rawConfig.controls["FrameDurationLimits"] = (100, 1000000000)
        cfg.videoConfig = CameraConfig()
        cfg.videoConfig.buffer_count = 6
        cfg.videoConfig.id = "VIDO"
        cfg.videoConfig.use_case = "Video"
        cfg.videoConfig.buffer_count = 6
        cfg.videoConfig.encode = "main"
        cfg.videoConfig.controls["FrameDurationLimits"] = (33333, 33333)
        cfg._cameraConfigs = []
        cfg.triggerConfig = TriggerConfig()
        cfg.serverConfig = ServerConfig()
        sc = cfg.serverConfig
        sc.photoRoot = photoRoot
        if sc.raspiModelLower5:
            cfg.liveViewConfig.format = "YUV420"
        if sc.raspiModelFull.startswith("Raspberry Pi Zero") \
        or sc.raspiModelFull.startswith("Raspberry Pi 4") \
        or sc.raspiModelFull.startswith("Raspberry Pi 3") \
        or sc.raspiModelFull.startswith("Raspberry Pi 2") \
        or sc.raspiModelFull.startswith("Raspberry Pi 1"):
            # For Pi Zero and 4 reduce buffer_count defaults for live view and video
            cfg.liveViewConfig.buffer_count = 2
            cfg.videoConfig.buffer_count = 2
        cfg.streamingCfg = {}
        
        sc.isVideoRecording = False
        sc.isAudioRecording = False
        sc.isTriggerRecording = False
        sc.isPhotoSeriesRecording = False
        sc.isLiveStream = False
        sc.isLiveStream2 = False
        sc.checkMicrophone()
        sc.checkEnvironment()
        sc.curMenu = "settings"
        
        Camera.cam = None
        Camera.cam2 = None
        Camera.camNum = -1
        Camera.camNum2 = -1
        Camera.ctrl = None
        Camera.ctrl2 = None
        Camera.videoOutput = None
        Camera.prgVideoOutput = None
        Camera.photoSeries = None
        Camera.thread = None
        Camera.thread2 = None
        Camera.liveViewDeactivated = False
        Camera.videoThread = None
        Camera.photoSeriesThread = None
        Camera.frame = None
        Camera.frame2 = None
        Camera.last_access = 0
        Camera.last_access2 = 0
        Camera.stopRequested = False
        Camera.stopRequested2 = False
        Camera.stopVideoRequested = False
        Camera.videoDuration = 0
        Camera.stopPhotoSeriesRequested = False
        Camera.event = CameraEvent()
        Camera.event2 = None
        Camera._instance = None
        
        msg = "Server configuration has been reset to default values"
        flash(msg)
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los)

@bp.route("/remove_users", methods=("GET", "POST"))
@login_required
def remove_users():
    logger.debug("In remove_users")
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    sc.lastSettingsTab = "settingsusers"
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    if request.method == "POST":
        cnt = 0
        msg = None
        if not msg:
            for user in g.users:
                if request.form.get("sel_" + str(user["id"])) is not None:
                    if user["id"] == g.user["id"]:
                        msg = "The active user cannot be removed"
                        break
                    else:
                        cnt += 1
        if not msg:
            logger.debug("Request to remove %s users", cnt)
            if cnt > 0:
                db = get_db()
                if cnt < len(g.users):
                    while cnt > 0:
                        logger.debug("cnt: %s", cnt)
                        userDel = None
                        for user in g.users:
                            logger.debug("Trying user %s %s", user["id"], user["username"])
                            if request.form.get("sel_" + str(user["id"])) is not None:
                                userDel =user["id"]
                                logger.debug("User selected")
                                break
                            else:
                                logger.debug("User not selected")
                        if userDel:
                            logger.debug("Removing user with id %s", userDel)
                            db.execute("DELETE FROM user WHERE id = ?", (userDel,)).fetchone
                            db.commit()
                            g.nrUsers = db.execute("SELECT count(*) FROM user").fetchone()[0]
                            logger.debug("Found %s users", g.nrUsers)
                            g.users = db.execute("SELECT * FROM user").fetchall()
                            for user in g.users:
                                logger.debug("Found user: ID: %s, UserName: %s", user["id"], user["username"])
                            cnt -= 1
                else:
                    msg="At least one user must remain"
                    flash(msg)
            else:
                msg="No users were selected"
                flash(msg)
        else:
            flash(msg)
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los)

@bp.route("/register_user", methods=("GET", "POST"))
@login_required
def register_user():
    logger.debug("In register_user")
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    sc.lastSettingsTab = "settingsusers"
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    if request.method == "POST":
        return render_template("auth/register.html", sc=sc, cp=cp)
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los)

@bp.route("/store_config", methods=("GET", "POST"))
@login_required
def store_config():
    logger.debug("In store_config")
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    sc.lastSettingsTab = "settingsconfig"
    if request.method == "POST":
        cfgPath = current_app.static_folder + "/config"
        # Initialize the Photo viewer list
        sc = cfg.serverConfig
        sc.pvList = []
        sc.updateStreamingClients()
        cfg.persist(cfgPath)
        msg = "Configuration stored under " + cfgPath
        flash(msg)
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los)

@bp.route("/load_config", methods=("GET", "POST"))
@login_required
def load_config():
    logger.debug("In load_config")
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    sc.lastSettingsTab = "settingsconfig"
    if request.method == "POST":
        cfg.loadConfig(cfgPath)
        msg = "Configuration loaded from " + cfgPath
        flash(msg)
        Camera().restartLiveStream()
        if Camera().cam2:
            Camera().restartLiveStream2()
        cam = Camera()
        cfg = CameraCfg()
        cs = cfg.cameras
        sc = cfg.serverConfig
        sc.checkMicrophone()
        cp = cfg.cameraProperties
        sc.curMenu = "settings"
        cfgPath = current_app.static_folder + "/config"
        los = getLoadConfigOnStart(cfgPath)
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los)

def getLoadConfigOnStart(cfgPath: str) -> bool:
    logger.debug("getLoadConfigOnStart")
    res = False
    if cfgPath:
        if os.path.exists(cfgPath):
            fp = cfgPath + "/_loadConfigOnStart.txt"
            if os.path.exists(fp):
                res = True
    logger.debug("getLoadConfigOnStart: %s", res)
    return res

def setLoadConfigOnStart(cfgPath: str, value: bool):
    logger.debug("setLoadConfigOnStart - value: %s", value)
    if cfgPath:
        if not os.path.exists(cfgPath):
            os.makedirs(cfgPath, exist_ok=True)
    fp = cfgPath + "/_loadConfigOnStart.txt"
    if value == True:
        Path(fp).touch()
    else:
        if os.path.exists(fp):
            os.remove(fp)

@bp.route("/loadConfigOnStart", methods=("GET", "POST"))
@login_required
def loadConfigOnStart():
    logger.debug("In loadConfigOnStart")
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    sc.lastSettingsTab = "settingsconfig"
    if request.method == "POST":
        cb = not request.form.get("loadconfigonstartcb") is None
        setLoadConfigOnStart(cfgPath, cb)
        los = getLoadConfigOnStart(cfgPath)
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los)
    
@bp.route('/shutdown', methods=("GET", "POST"))
@login_required
def shutdown():
    logger.debug("In shutdown")
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    sc.lastSettingsTab = "settingsconfig"
    if request.method == "POST":
        shutdown = request.environ.get('werkzeug.server.shutdown')
        if shutdown is None:
            msg = "raspiCamSrv is not running with Werkzeug Server. Shut down manually."
        else:
            shutdown()
            msg = "Server shutting down ..."
        flash(msg)
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los)

@bp.route("/api_config", methods=("GET", "POST"))
@login_required
def api_config():
    logger.debug("In api_config")
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    sc.lastSettingsTab = "settingsapi"
    if request.method == "POST":
        msg = ""
        sc = cfg.serverConfig
        jwtAccessTokenExpirationMin = sc.jwtAccessTokenExpirationMin
        jwtRefreshTokenExpirationDays = sc.jwtRefreshTokenExpirationDays
        jwtKeyStore = request.form["jwtkeystore"]
        logger.debug("api_config - jwtKeyStore=%s", jwtKeyStore)
        if jwtKeyStore != "":
            if os.path.exists(jwtKeyStore):
                if os.path.isfile(jwtKeyStore):
                    with open(jwtKeyStore) as f:
                        try:
                            secrets = json.load(f)
                            sc.jwtKeyStore = jwtKeyStore
                            logger.debug("api_config - jwtKeyStore successfully accessed")
                        except Exception as e:
                            msg = f"Error when accessing JWT Secret Key File: {e}"
                else:
                    sc.jwtKeyStore = jwtKeyStore
            else:
                sc.jwtKeyStore = jwtKeyStore
        else:
            sc.jwtKeyStore = ""
        sc.jwtAccessTokenExpirationMin = int(request.form["jwtaccesstokenexpirationmin"])
        sc.jwtRefreshTokenExpirationDays = int(request.form["jwtrefreshtokenexpirationdays"])
        if msg == "":
            (secretKey, err, msg) = sc.checkJwtSettings()
            logger.debug("api_config - secrKey = %s, err = %s, msg = %s", secretKey, err, msg)
            if not err is None:
                msg = "ERROR: " + err
        if msg != "":
            flash(msg)
        if sc.API_active == True:
            if sc.jwtAuthenticationActive == True:
                if jwtAccessTokenExpirationMin != sc.jwtAccessTokenExpirationMin \
                or jwtRefreshTokenExpirationDays != sc.jwtRefreshTokenExpirationDays:
                    sc.jwtAuthenticationActive = False
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los)

@bp.route("/generate_token", methods=("GET", "POST"))
@login_required
def generate_token():
    logger.debug("In generate_token")
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    sc.lastSettingsTab = "settingsapi"
    if request.method == "POST":
        access_token = create_access_token(identity=g.user['username'])
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los, access_token=access_token)
    
@bp.route('/vbutton_dimensions', methods=("GET", "POST"))
@login_required
def vbutton_dimensions():
    logger.debug("In vbutton_dimensions")
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    sc.lastSettingsTab = "settingsvbuttons"
    if request.method == "POST":
        msg = ""
        if request.form["vbuttonsrows"]:
            vButtonsRows = int(request.form["vbuttonsrows"])
        else:
            msg = "Please enter a valid number of rows"
        if request.form["vbuttonscols"]:
            vButtonsCols = int(request.form["vbuttonscols"])
        else:
            msg = "Please enter a valid number of columns"
        if msg == "":
            if vButtonsRows == 0 \
            or vButtonsCols == 0:
                sc.vButtonsCols = vButtonsCols
                sc.vButtonsRows = vButtonsRows
                sc.vButtons = []
            else:
                vButtons = []
                for r in range(0, vButtonsRows):
                    row = []
                    for c in range(0, vButtonsCols):
                        if r < sc.vButtonsRows and c < sc.vButtonsCols:
                            btn = sc.vButtons[r][c]
                        else:
                            btn = vButton()
                        btn.row = r
                        btn.col = c
                        row.append(btn)
                    vButtons.append(row)
                sc.vButtonsCols = vButtonsCols
                sc.vButtonsRows = vButtonsRows
                sc.vButtons = vButtons
                sc.vButtonHasCommandLine = not request.form.get("vbuttonhascommandline") is None
        if msg != "":
            flash(msg)
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los)
    
@bp.route('/vbutton_settings', methods=("GET", "POST"))
@login_required
def vbutton_settings():
    logger.debug("In vbutton_settings")
    g.hostname = request.host
    g.version = version
    cam = Camera()
    cfg = CameraCfg()
    cs = cfg.cameras
    sc = cfg.serverConfig
    cfgPath = current_app.static_folder + "/config"
    los = getLoadConfigOnStart(cfgPath)
    # Check connection and access of microphone
    sc.checkMicrophone()
    cp = cfg.cameraProperties
    sc.curMenu = "settings"
    sc.lastSettingsTab = "settingsvbuttons"
    if request.method == "POST":
        msg = ""
        for r in range(0, sc.vButtonsRows):
            for c in range(0, sc.vButtonsCols):
                btn = sc.vButtons[r][c]
                visibleId = f"vbtn_{btn.row}{ btn.col }_visible"
                btn.isVisible = not request.form.get(visibleId) is None
                buttonTextKey = f"vbtn_{btn.row}{btn.col}_buttontext"
                btn.buttonText = request.form[buttonTextKey]
                buttonExecKey = f"vbtn_{btn.row}{btn.col}_buttonexec"
                btn.buttonExec = request.form[buttonExecKey]
                buttonShapeKey = f"vbtn_{btn.row}{btn.col}_shape"
                btn.buttonShape = request.form[buttonShapeKey]
                buttonColorKey = f"vbtn_{btn.row}{btn.col}_color"
                btn.buttonColor = request.form[buttonColorKey]
                confirmId = f"vbtn_{btn.row}{ btn.col }_confirm"
                btn.needsConfirm = not request.form.get(confirmId) is None
                sc.vButtons[r][c] = btn
        if msg != "":
            flash(msg)
    return render_template("settings/main.html", sc=sc, cp=cp, cs=cs, los=los)
