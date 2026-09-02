from collections.abc import Collection


PROFILE_HOSTS = {
    "github": "github.com",
    "linkedin": "linkedin.com",
    "devpost": "devpost.com",
}

COUNTRY_OPTIONS = frozenset(
    {
        "Canada", "United States", "United Kingdom", "India", "Australia",
        "Germany", "France", "China", "Japan", "South Korea", "Brazil",
        "Mexico", "Italy", "Spain", "Russia", "South Africa", "New Zealand",
        "Netherlands", "Sweden", "Norway", "Denmark", "Finland", "Switzerland",
        "Turkey", "Saudi Arabia", "United Arab Emirates", "Singapore", "Malaysia",
        "Indonesia", "Thailand", "Vietnam", "Philippines", "Argentina", "Chile",
        "Colombia", "Egypt", "Nigeria", "Kenya", "Other",
    }
)

SCHOOL_OPTIONS = frozenset(
    {
        "Acadia University", "Algoma University", "Athabasca University",
        "Bishop's University", "Brandon University", "Brock University",
        "Cape Breton University", "Carleton University", "Concordia University",
        "Dalhousie University", "Emily Carr University of Art and Design",
        "First Nations University of Canada", "Kwantlen Polytechnic University",
        "Lakehead University", "Laval University", "Laurentian University",
        "MacEwan University", "McGill University", "McMaster University",
        "Memorial University of Newfoundland", "Mount Allison University",
        "Mount Royal University", "Mount Saint Vincent University",
        "Nipissing University", "NSCAD University", "OCAD University",
        "Ontario Tech University", "Polytechnique Montréal", "Queen's University",
        "Royal Military College of Canada", "Royal Roads University",
        "Saint Mary's University", "Simon Fraser University",
        "St. Francis Xavier University", "St. Thomas University",
        "Thompson Rivers University", "Toronto Metropolitan University",
        "Trent University", "University of Alberta", "University of British Columbia",
        "University of Calgary", "University of Guelph", "University of King's College",
        "University of Lethbridge", "University of Manitoba",
        "University of New Brunswick", "University of Northern British Columbia",
        "University of Ottawa", "University of Prince Edward Island",
        "University of Regina", "University of Saskatchewan",
        "University of Toronto (St. George)",
        "University of Toronto (Scarborough)",
        "University of Toronto (Mississauga)", "University of Victoria",
        "University of Waterloo", "University of Windsor", "University of Winnipeg",
        "Vancouver Island University", "Western University",
        "Wilfrid Laurier University", "York University", "Other",
    }
)

MAJOR_OPTIONS = frozenset(
    {
        "Computer Science", "Software Engineering", "Mechanical Engineering",
        "Electrical Engineering", "Civil Engineering", "Business Administration",
        "Accounting", "Finance", "Marketing", "Economics", "Biology",
        "Biotechnology", "Chemistry", "Physics", "Mathematics", "Statistics",
        "Psychology", "Sociology", "Political Science", "History", "Philosophy",
        "English Literature", "Education", "Environmental Science", "Nursing",
        "Medicine", "Law", "Architecture", "Fine Arts", "Music", "Theatre", "Other",
    }
)

EDUCATION_LEVEL_OPTIONS = frozenset(
    {
        "High School", "Freshman - Undergraduate", "Sophomore - Undergraduate",
        "Junior - Undergraduate", "Senior - Undergraduate", "Graduate", "PhD", "Other",
    }
)
GENDER_OPTIONS = frozenset(
    {"Male", "Female", "Non-binary", "Other", "Prefer not to say"}
)
RACE_ETHNICITY_OPTIONS = frozenset(
    {
        "Black/People of African Descent", "Arab/Middle Eastern",
        "East Asian (e.g. China, Japan, Korea)",
        "South/Southeast Asian (e.g. India, Pakistan, Sri Lanka, Philippines, Thailand)",
        "Indigenous Person of Canada", "Latinx", "West Asian (e.g. Iran, Afghanistan)",
        "White/People of European Descent", "Other", "Prefer not to say",
    }
)
YES_NO_OPTIONS = frozenset({"Yes", "No", "Prefer not to say"})
SKILL_LEVEL_OPTIONS = frozenset({"Beginner", "Intermediate", "Advanced", "Expert"})

CHOICE_OPTIONS: dict[str, Collection[str]] = {
    "Country": COUNTRY_OPTIONS,
    "School Name": SCHOOL_OPTIONS,
    "Major": MAJOR_OPTIONS,
    "Current Level of Study": EDUCATION_LEVEL_OPTIONS,
    "Gender": GENDER_OPTIONS,
    "Part of the LGBTQ+ Community": YES_NO_OPTIONS,
    "Person with Disabilities?": YES_NO_OPTIONS,
    "Avatar": frozenset({"owl", "bear", "chipmunk", "raccoon"}),
    "Accessory": frozenset({"hat", "book", "potion"}),
    "UI/UX Design": SKILL_LEVEL_OPTIONS,
    "Frontend Development": SKILL_LEVEL_OPTIONS,
    "Backend Development": SKILL_LEVEL_OPTIONS,
    "Fullstack Development": SKILL_LEVEL_OPTIONS,
    "Project Management": SKILL_LEVEL_OPTIONS,
    "Web, Crypto, Blockchain": SKILL_LEVEL_OPTIONS,
    "Cybersecurity": SKILL_LEVEL_OPTIONS,
    "Machine Learning": SKILL_LEVEL_OPTIONS,
    "T-Shirt Size": frozenset({"S", "M", "L", "XL"}),
    "MLH Code of Conduct": frozenset({"true", "false"}),
    "MLH Privacy Policy, MLH Contest Terms and Conditions": frozenset(
        {"true", "false"}
    ),
    "MLH Event Communication": frozenset({"true", "false"}),
    "Hack the Valley Consent Form Agreement": frozenset({"true", "false"}),
}

INTEGER_RANGES = {
    "Expected Graduation Year": (2000, 2100),
    "Age": (1, 120),
    "Hackathon Count?": (0, 1000),
}
