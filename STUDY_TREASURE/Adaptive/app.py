
from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import random
import time

app = Flask(__name__)
app.secret_key = "study-treasure-change-this-secret"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Prakrati11",
    "database": "STUDY_TREASURE"
}

DIFFICULTIES = ["Easy", "Moderate", "Difficult"]


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def change_difficulty(current, step):
    index = DIFFICULTIES.index(current)
    index = max(0, min(2, index + step))
    return DIFFICULTIES[index]


def get_question():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    class_level = session["class_level"]
    subject = session["subject"]
    chapter = session["chapter"]
    difficulty = session["difficulty"]
    asked = session["asked"]

    subjects = ["Physics", "Chemistry"] if subject == "Science" else [subject]

    placeholders = ", ".join(["%s"] * len(subjects))
    query = f"""
        SELECT question_id, question, option_a, option_b,
               option_c, option_d, difficulty, chapter
        FROM quiz_questions
        WHERE class_level = %s
          AND subject IN ({placeholders})
    """

    params = [class_level] + subjects

    if chapter != "All Topics":
        query += " AND chapter = %s"
        params.append(chapter)

    if asked:
        query += " AND question_id NOT IN (" + ", ".join(["%s"] * len(asked)) + ")"
        params.extend(asked)

    difficulty_order = [
        difficulty,
        *[d for d in DIFFICULTIES if d != difficulty]
    ]

    for level in difficulty_order:
        level_query = query + " AND difficulty = %s ORDER BY RAND() LIMIT 1"
        cursor.execute(level_query, params + [level])
        question = cursor.fetchone()

        if question:
            break

    cursor.close()
    conn.close()
    return question


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/start", methods=["POST"])
def start_quiz():
    try:
        class_level = int(request.form["class_level"])
    except (ValueError, KeyError):
        return redirect(url_for("home"))

    subject = request.form.get("subject")
    chapter = request.form.get("chapter", "All Topics")

    if class_level not in [11, 12]:
        return redirect(url_for("home"))

    if subject not in ["Mathematics", "Physics", "Chemistry", "Science"]:
        return redirect(url_for("home"))

    session.clear()
    session["class_level"] = class_level
    session["subject"] = subject
    session["chapter"] = chapter
    session["difficulty"] = "Easy"
    session["asked"] = []
    session["current_id"] = None
    session["question_count"] = 0
    session["score"] = 0
    session["correct_streak"] = 0
    session["wrong_streak"] = 0
    session["performance_points"] = 0
    session["answers"] = []

    return redirect(url_for("quiz"))


@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    if "class_level" not in session:
        return redirect(url_for("home"))

    if request.method == "POST":
        current_id = session.get("current_id")

        if current_id is None:
            return redirect(url_for("quiz"))

        selected = request.form.get("answer")
        try:
            response_time = max(0, float(request.form.get("elapsed", 0)))
        except ValueError:
            response_time = 0

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT correct_option FROM quiz_questions WHERE question_id = %s",
            (current_id,)
        )
        answer_row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not answer_row:
            session["current_id"] = None
            return redirect(url_for("quiz"))

        correct = selected == answer_row["correct_option"]
        session["question_count"] += 1

        if correct:
            session["score"] += 1
            session["correct_streak"] += 1
            session["wrong_streak"] = 0
            session["performance_points"] += 1 if response_time <= 20 else 0
        else:
            session["wrong_streak"] += 1
            session["correct_streak"] = 0
            session["performance_points"] -= 1

        session["answers"].append({
            "question_id": current_id,
            "correct": correct,
            "time": round(response_time, 1)
        })

        old_difficulty = session["difficulty"]

        if session["correct_streak"] >= 3:
            session["difficulty"] = change_difficulty(old_difficulty, 1)
            session["correct_streak"] = 0
            session["performance_points"] = 0

        elif session["wrong_streak"] >= 3:
            session["difficulty"] = change_difficulty(old_difficulty, -1)
            session["wrong_streak"] = 0
            session["performance_points"] = 0

        elif session["performance_points"] >= 3:
            session["difficulty"] = change_difficulty(old_difficulty, 1)
            session["performance_points"] = 0

        elif session["performance_points"] <= -3:
            session["difficulty"] = change_difficulty(old_difficulty, -1)
            session["performance_points"] = 0

        session["current_id"] = None

        if session["question_count"] >= 5:
            return redirect(url_for("result"))

        return redirect(url_for("quiz"))

    if session["question_count"] >= 5:
        return redirect(url_for("result"))

    current_id = session.get("current_id")
    question = None

    if current_id is not None:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT question_id, question, option_a, option_b,
                   option_c, option_d, difficulty, chapter
            FROM quiz_questions
            WHERE question_id = %s
        """, (current_id,))
        question = cursor.fetchone()
        cursor.close()
        conn.close()

    if question is None:
        question = get_question()

    if question is None:
        return render_template(
            "result.html",
            score=session["score"],
            total=session["question_count"],
            accuracy=round(
                session["score"] / session["question_count"] * 100, 1
            ) if session["question_count"] else 0,
            answers=session["answers"],
            message="Not enough unused questions are available for these choices."
        )

    if question["question_id"] not in session["asked"]:
        session["asked"].append(question["question_id"])

    session["current_id"] = question["question_id"]

    return render_template(
        "quiz.html",
        question=question,
        number=session["question_count"] + 1,
        difficulty=session["difficulty"],
        total=5
    )


@app.route("/result")
def result():
    if "class_level" not in session:
        return redirect(url_for("home"))

    total = session["question_count"]
    score = session["score"]
    accuracy = round(score / total * 100, 1) if total else 0

    return render_template(
        "result.html",
        score=score,
        total=total,
        accuracy=accuracy,
        answers=session["answers"],
        message=None
    )


if __name__ == "__main__":
    app.run(debug=True)
