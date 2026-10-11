
import os
import uuid
from pathlib import Path

import mysql.connector
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash
)
from pypdf import PdfReader
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "local-development-key-change-me"
)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Subha@1234",
    "database": "resume_matcher",
}

SKILLS = [
    "Python", "Java", "C++", "C", "HTML", "CSS",
    "JavaScript", "Flask", "Django", "MySQL", "SQL",
    "MongoDB", "React", "Node.js", "Tkinter", "Git",
    "GitHub", "REST API", "Pandas", "NumPy",
    "Machine Learning", "Data Analysis", "Data Science",
    "Communication", "Teamwork", "Problem Solving",
    "Excel", "Power BI", "AWS", "Docker", "Linux",
    "Bootstrap", "PostgreSQL", "FastAPI", "OOP"
]


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def extract_skills(text):
    """Find known skills in text without matching partial words."""
    found = []
    text_lower = text.lower()

    for skill in SKILLS:
        skill_lower = skill.lower()

        # Avoid matching C inside words such as "communication".
        if skill_lower == "c":
            import re
            if re.search(r"(?<!\w)c(?!\w)", text_lower):
                found.append(skill)
        else:
            import re
            pattern = r"(?<!\w)" + re.escape(skill_lower) + r"(?!\w)"
            if re.search(pattern, text_lower):
                found.append(skill)

    return found


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    candidate_name = request.form.get("candidate_name", "").strip()
    job_description = request.form.get("job_description", "").strip()
    resume = request.files.get("resume")

    if not candidate_name or not job_description or not resume:
        flash("Please fill in all fields and upload a PDF resume.", "error")
        return redirect(url_for("index"))

    if len(candidate_name) > 100:
        flash("Candidate name must be 100 characters or fewer.", "error")
        return redirect(url_for("index"))

    if not resume.filename:
        flash("Please select a resume PDF.", "error")
        return redirect(url_for("index"))

    safe_name = secure_filename(resume.filename)

    if not safe_name or Path(safe_name).suffix.lower() != ".pdf":
        flash("Only PDF resumes are accepted.", "error")
        return redirect(url_for("index"))

    saved_path = None

    try:
        # Confirm that the uploaded file begins with a PDF signature.
        file_bytes = resume.read()
        if not file_bytes.startswith(b"%PDF-"):
            flash("The uploaded file does not appear to be a valid PDF.", "error")
            return redirect(url_for("index"))

        saved_name = f"{uuid.uuid4().hex}.pdf"
        saved_path = UPLOAD_FOLDER / saved_name
        saved_path.write_bytes(file_bytes)

        reader = PdfReader(str(saved_path))

        if reader.is_encrypted:
            flash("Please upload an unlocked PDF resume.", "error")
            return redirect(url_for("index"))

        resume_text = "\n".join(
            page.extract_text() or "" for page in reader.pages
        )

        if not resume_text.strip():
            flash(
                "No selectable text was found. Please use a text-based PDF.",
                "error"
            )
            return redirect(url_for("index"))

        resume_skills = extract_skills(resume_text)
        required_skills = extract_skills(job_description)

        if not required_skills:
            flash(
                "No supported skills were found in the job description. "
                "Add skills such as Python, Flask, or MySQL.",
                "error"
            )
            return redirect(url_for("index"))

        matched_skills = [
            skill for skill in required_skills
            if skill in resume_skills
        ]
        missing_skills = [
            skill for skill in required_skills
            if skill not in resume_skills
        ]

        score = round(
            len(matched_skills) / len(required_skills) * 100, 2
        )

        connection = get_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO analysis_results (
                candidate_name, resume_filename, resume_skills,
                job_description, required_skills, matched_skills,
                missing_skills, match_score
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            candidate_name,
            safe_name,
            ", ".join(resume_skills),
            job_description,
            ", ".join(required_skills),
            ", ".join(matched_skills),
            ", ".join(missing_skills),
            score,
        )

        cursor.execute(query, values)
        connection.commit()
        result_id = cursor.lastrowid

        cursor.close()
        connection.close()

        return redirect(url_for("result", result_id=result_id))

    except mysql.connector.Error as error:
        app.logger.exception("Database error")
        flash(
            "Could not save the analysis to MySQL. Check your database "
            "credentials, server, and table setup.",
            "error"
        )
        return redirect(url_for("index"))

    except Exception:
        app.logger.exception("Resume analysis failed")
        flash(
            "Could not analyze this PDF. Please try another text-based PDF.",
            "error"
        )
        return redirect(url_for("index"))

    finally:
        if saved_path and saved_path.exists():
            try:
                saved_path.unlink()
            except OSError:
                app.logger.warning("Could not remove temporary uploaded PDF.")


@app.route("/result/<int:result_id>")
def result(result_id):
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM analysis_results WHERE id = %s",
            (result_id,)
        )
        analysis = cursor.fetchone()

        if analysis is None:
            flash("Analysis result not found.", "error")
            return redirect(url_for("index"))

        return render_template("result.html", analysis=analysis)

    except mysql.connector.Error:
        app.logger.exception("Could not load analysis result")
        flash("Could not load the result from MySQL.", "error")
        return redirect(url_for("index"))

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.route("/history")
def history():
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, candidate_name, resume_filename,
                   match_score, created_at
            FROM analysis_results
            ORDER BY created_at DESC
        """)
        records = cursor.fetchall()
        return render_template("history.html", records=records)

    except mysql.connector.Error:
        app.logger.exception("Could not load analysis history")
        flash("Could not load history. Check your MySQL connection.", "error")
        return redirect(url_for("index"))

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@app.errorhandler(413)
def file_too_large(error):
    flash("The PDF is too large. Maximum upload size is 5 MB.", "error")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
