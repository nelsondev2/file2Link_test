from flask import Blueprint, jsonify, request
from fileservice import fileservice
from loadmanager import loadmanager
from config import MAXFILESIZEMB, MAXUSERQUOTAMB
from quotaservice import quotaservice

apibp = Blueprint("api", name, urlprefix="/api")

@api_bp.route("/system/status", methods=["GET"])
def apisystemstatus():
    status = loadmanager.getstatus()
    return jsonify({
        "status": "online",
        "cpupercent": status["cpupercent"],
        "memorypercent": status["memorypercent"],
        "activeprocesses": status["activeprocesses"],
        "maxprocesses": status["maxprocesses"],
        "maxfilesizemb": MAXFILESIZEMB,
        "maxuserquotamb": MAXUSERQUOTAMB
    })

@apibp.route("/user/<int:userid>/stats", methods=["GET"])
def apiuserstats(user_id):
    usedbytes, usedmb, percent = quotaservice.getuserusage(userid)
    downloads = fileservice.listuserfiles(userid, "downloads")
    packed = fileservice.listuserfiles(userid, "packed")
    return jsonify({
        "userid": userid,
        "usedbytes": usedbytes,
        "usedmb": usedmb,
        "used_percent": percent,
        "downloads_count": len(downloads),
        "packed_count": len(packed)
    })

@apibp.route("/user/<int:userid>/files", methods=["GET"])
def apiuserfiles(user_id):
    folder = request.args.get("folder", "downloads")
    if folder not in ["downloads", "packed"]:
        folder = "downloads"
    files = fileservice.listuserfiles(userid, folder)
    return jsonify({
        "userid": userid,
        "folder": folder,
        "files": files
    })