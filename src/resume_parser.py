from pathlib import Path

from docx import Document
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt"
}


def find_resume_file():
    """
    Find the first supported resume file
    inside data/resume/.
    """

    base_dir = Path(__file__).resolve().parent.parent
    resume_dir = base_dir / "data" / "resume"

    if not resume_dir.exists():
        return None

    files = [
        file
        for file in resume_dir.iterdir()
        if file.is_file()
        and file.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        return None

    files.sort()

    return files[0]


def extract_text_from_pdf(file_path):
    """
    Extract text from a PDF resume.
    """

    reader = PdfReader(str(file_path))

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n".join(pages)


def extract_text_from_docx(file_path):
    """
    Extract text from a DOCX resume.
    """

    document = Document(str(file_path))

    paragraphs = [
        paragraph.text
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]

    return "\n".join(paragraphs)


def extract_text_from_txt(file_path):
    """
    Extract text from a TXT resume.
    """

    return file_path.read_text(
        encoding="utf-8"
    )


def extract_resume_text(file_path):
    """
    Extract resume text based on file type.
    """

    extension = file_path.suffix.lower()

    if extension == ".pdf":
        return extract_text_from_pdf(
            file_path
        )

    if extension == ".docx":
        return extract_text_from_docx(
            file_path
        )

    if extension == ".txt":
        return extract_text_from_txt(
            file_path
        )

    raise ValueError(
        f"Unsupported resume type: "
        f"{extension}"
    )


def normalize_text(text):
    """
    Normalize text for keyword matching.
    """

    if not text:
        return ""

    return (
        str(text)
        .lower()
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )


def extract_skills(resume_text):
    """
    Extract known skills that are explicitly
    present in the resume.

    Never invent skills.
    """

    text = normalize_text(
        resume_text
    )

    skill_dictionary = {
        "Python": [
            "python"
        ],
        "SQL": [
            "sql"
        ],
        "Excel": [
            "excel",
            "microsoft excel"
        ],
        "PowerPoint": [
            "powerpoint",
            "microsoft powerpoint"
        ],
        "Tableau": [
            "tableau"
        ],
        "Power BI": [
            "power bi",
            "powerbi"
        ],
        "R": [
            " r ",
            "\nr ",
            "r programming"
        ],
        "Statistics": [
            "statistics",
            "statistical"
        ],
        "Data Analytics": [
            "data analytics",
            "data analysis",
            "analytics"
        ],
        "Financial Modeling": [
            "financial modeling",
            "financial modelling",
            "financial model"
        ],
        "Valuation": [
            "valuation",
            "dcf",
            "discounted cash flow"
        ],
        "Machine Learning": [
            "machine learning"
        ],
        "Capital IQ": [
            "capital iq",
            "s&p capital iq"
        ],
        "Bloomberg": [
            "bloomberg"
        ],
        "PitchBook": [
            "pitchbook"
        ]
    }

    matched_skills = []

    padded_text = f" {text} "

    for skill, aliases in skill_dictionary.items():

        if any(
            alias in padded_text
            for alias in aliases
        ):
            matched_skills.append(
                skill
            )

    return matched_skills


def extract_education(resume_text):
    """
    Extract simple education-related signals.
    """

    text = normalize_text(
        resume_text
    )

    education = []

    bachelor_terms = [
        "bachelor",
        "b.s.",
        "b.a.",
        "bs ",
        "ba "
    ]

    master_terms = [
        "master",
        "m.s.",
        "ms ",
        "mba"
    ]

    if any(
        term in text
        for term in bachelor_terms
    ):
        education.append(
            "Bachelor's degree"
        )

    if any(
        term in text
        for term in master_terms
    ):
        education.append(
            "Master's degree"
        )

    return education


def extract_experience_keywords(
    resume_text
):
    """
    Extract experience-domain keywords that
    explicitly appear in the resume.
    """

    text = normalize_text(
        resume_text
    )

    keywords = {
        "Investment Banking": [
            "investment banking",
            "ibd"
        ],
        "Private Equity": [
            "private equity"
        ],
        "Venture Capital": [
            "venture capital",
            " vc "
        ],
        "Equity Research": [
            "equity research"
        ],
        "Financial Analysis": [
            "financial analysis",
            "financial analyst"
        ],
        "Valuation": [
            "valuation",
            "dcf",
            "comparable companies",
            "comps"
        ],
        "Due Diligence": [
            "due diligence"
        ],
        "Market Research": [
            "market research"
        ],
        "Data Analysis": [
            "data analysis",
            "analytics"
        ],
        "Risk Analysis": [
            "risk analysis",
            "risk management"
        ]
    }

    matched = []

    padded_text = f" {text} "

    for category, aliases in keywords.items():

        if any(
            alias in padded_text
            for alias in aliases
        ):
            matched.append(
                category
            )

    return matched


def parse_resume():
    """
    Locate and parse the user's resume.
    """

    resume_file = find_resume_file()

    if resume_file is None:
        return {
            "file_found": False,
            "file_name": None,
            "raw_text": "",
            "skills": [],
            "education": [],
            "experience_keywords": []
        }

    try:
        raw_text = extract_resume_text(
            resume_file
        )

    except Exception as error:
        return {
            "file_found": True,
            "file_name": resume_file.name,
            "error": str(error),
            "raw_text": "",
            "skills": [],
            "education": [],
            "experience_keywords": []
        }

    return {
        "file_found": True,
        "file_name": resume_file.name,
        "raw_text": raw_text,
        "skills": extract_skills(
            raw_text
        ),
        "education": extract_education(
            raw_text
        ),
        "experience_keywords":
            extract_experience_keywords(
                raw_text
            )
    }


def display_resume_summary(
    resume_data
):
    """
    Print parsed resume information.
    """

    print()
    print(
        "=== Resume Parser ==="
    )
    print()

    if not resume_data[
        "file_found"
    ]:
        print(
            "No resume found."
        )
        print(
            "Place a PDF, DOCX, or TXT "
            "resume inside data/resume/."
        )
        return

    print(
        f"Resume file: "
        f"{resume_data['file_name']}"
    )

    if resume_data.get(
        "error"
    ):
        print(
            f"Error: "
            f"{resume_data['error']}"
        )
        return

    print()

    print(
        "Detected Skills:"
    )

    if resume_data["skills"]:

        for skill in resume_data[
            "skills"
        ]:
            print(
                f"- {skill}"
            )

    else:
        print(
            "- None detected"
        )

    print()

    print(
        "Detected Education:"
    )

    if resume_data["education"]:

        for item in resume_data[
            "education"
        ]:
            print(
                f"- {item}"
            )

    else:
        print(
            "- None detected"
        )

    print()

    print(
        "Experience Keywords:"
    )

    if resume_data[
        "experience_keywords"
    ]:

        for item in resume_data[
            "experience_keywords"
        ]:
            print(
                f"- {item}"
            )

    else:
        print(
            "- None detected"
        )


if __name__ == "__main__":

    resume_data = parse_resume()

    display_resume_summary(
        resume_data
    )