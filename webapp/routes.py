# webapp/routes.py
from flask import Blueprint, render_template, jsonify
from . import database as dbsvc
from . import cover_letter as clsvc

web_bp = Blueprint("web", __name__)

@web_bp.route("/")
def index():
    jobs = dbsvc.get_jobs()
    return render_template("jobs.html", jobs=jobs)

@web_bp.route("/job_details/<int:job_id>")
def job_details(job_id):
    job = dbsvc.get_job(job_id)
    return jsonify(job)

@web_bp.route("/mark_applied/<int:job_id>", methods=["POST"])
def mark_applied(job_id):
    updated = dbsvc.update_flag(job_id, applied=1)
    return jsonify({"success": bool(updated)})

@web_bp.route("/mark_rejected/<int:job_id>", methods=["POST"])
def mark_rejected(job_id):
    updated = dbsvc.update_flag(job_id, rejected=1)
    return jsonify({"success": bool(updated)})

@web_bp.route("/mark_interview/<int:job_id>", methods=["POST"])
def mark_interview(job_id):
    updated = dbsvc.update_flag(job_id, interview=1)
    return jsonify({"success": bool(updated)})

@web_bp.route("/hide_job/<int:job_id>", methods=["POST"])
def hide_job(job_id):
    updated = dbsvc.update_flag(job_id, hidden=1)
    return jsonify({"success": bool(updated)})

@web_bp.route("/get_CoverLetter/<int:job_id>", methods=["POST"])
def get_cover_letter(job_id):
    cover = clsvc.generate_and_store_cover_letter(job_id)
    return jsonify({"cover_letter": cover})
