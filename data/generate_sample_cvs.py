"""Generate the fixed test set for the AI CV Checker:

- 16 synthetic candidate CVs as PDFs in data/sample_cvs/
- data/ground_truth.json with the exact structured facts behind each CV,
  used later to hand-build the evaluation gold set (Phase 3).

Most CVs use a clean single-column layout; two use deliberately awkward
layouts (two-column, table-based experience) to exercise the PDF parser.

Run:  backend/.venv/Scripts/python data/generate_sample_cvs.py
"""

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_DIR = Path(__file__).parent / "sample_cvs"
GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"

PROFILES = [
    {
        "id": "sarah_chen",
        "name": "Sarah Chen",
        "title": "Senior Backend Engineer",
        "email": "sarah.chen@example.com",
        "phone": "+961 70 123 456",
        "location": "Beirut, Lebanon",
        "layout": "standard",
        "summary": "Backend engineer with 7+ years building Python services at scale. "
        "Strong in API design, relational data modeling, and event-driven architectures. "
        "Led small teams and owns systems end-to-end, from design to on-call.",
        "experience": [
            {
                "company": "CloudMed",
                "role": "Senior Backend Engineer",
                "start": "Jan 2025",
                "end": "Present",
                "bullets": [
                    "Own the patient-records API (FastAPI, PostgreSQL) serving 2M requests/day.",
                    "Introduced async task pipeline with Celery and Redis, cutting report latency by 60%.",
                ],
            },
            {
                "company": "TechFlow",
                "role": "Senior Backend Engineer",
                "start": "Jul 2022",
                "end": "Dec 2024",
                "bullets": [
                    "Broke a Django monolith into 6 microservices communicating over Kafka.",
                    "Led a team of 4 engineers; established code review and CI standards.",
                    "Reduced p95 API latency from 800ms to 220ms through query optimization.",
                ],
            },
            {
                "company": "DataCorp",
                "role": "Backend Engineer",
                "start": "Mar 2019",
                "end": "Jun 2022",
                "bullets": [
                    "Built Django REST APIs for a B2B analytics product.",
                    "Designed the PostgreSQL schema powering customer-facing dashboards.",
                ],
            },
        ],
        "education": [
            {"degree": "BSc Computer Science", "school": "American University of Beirut", "year": "2018"}
        ],
        "skills": [
            "Python", "Django", "FastAPI", "PostgreSQL", "Redis", "Kafka",
            "Celery", "Docker", "AWS", "CI/CD",
        ],
        "languages": ["Arabic (native)", "English (fluent)", "French (intermediate)"],
        "certifications": ["AWS Certified Developer - Associate"],
    },
    {
        "id": "omar_haddad",
        "name": "Omar Haddad",
        "title": "Machine Learning Engineer",
        "email": "omar.haddad@example.com",
        "phone": "+971 50 234 567",
        "location": "Dubai, UAE",
        "layout": "standard",
        "summary": "ML engineer focused on taking models from notebook to production. "
        "Experience across computer vision and recommender systems, with solid MLOps practices.",
        "experience": [
            {
                "company": "RoadTech",
                "role": "Senior ML Engineer",
                "start": "Sep 2023",
                "end": "Present",
                "bullets": [
                    "Built the ride-recommendation system (PyTorch) lifting conversion by 12%.",
                    "Set up the feature store and MLflow-based experiment tracking for the ML team.",
                ],
            },
            {
                "company": "SightAI",
                "role": "ML Engineer",
                "start": "Feb 2021",
                "end": "Aug 2023",
                "bullets": [
                    "Trained and deployed object-detection models for retail shelf monitoring.",
                    "Deployed models to AWS SageMaker with automated retraining pipelines.",
                ],
            },
        ],
        "education": [
            {"degree": "MSc Data Science", "school": "University of Jordan", "year": "2020"},
            {"degree": "BSc Computer Science", "school": "University of Jordan", "year": "2018"},
        ],
        "skills": [
            "Python", "PyTorch", "scikit-learn", "MLflow", "SageMaker",
            "Docker", "Airflow", "SQL", "computer vision", "recommender systems",
        ],
        "languages": ["Arabic (native)", "English (fluent)"],
        "certifications": [],
    },
    {
        "id": "elena_petrova",
        "name": "Elena Petrova",
        "title": "Senior Frontend Engineer",
        "email": "elena.petrova@example.com",
        "phone": "+49 152 345 6789",
        "location": "Berlin, Germany",
        "layout": "standard",
        "summary": "Frontend engineer specializing in React and TypeScript. "
        "Cares deeply about performance, accessibility, and design systems that scale across teams.",
        "experience": [
            {
                "company": "ShopHive",
                "role": "Senior Frontend Engineer",
                "start": "Apr 2023",
                "end": "Present",
                "bullets": [
                    "Lead frontend for the checkout flow (Next.js), improving Core Web Vitals to green across the board.",
                    "Drove the accessibility program to WCAG 2.1 AA compliance.",
                ],
            },
            {
                "company": "PixelWorks",
                "role": "Frontend Developer",
                "start": "Jun 2020",
                "end": "Mar 2023",
                "bullets": [
                    "Built and maintained the company design system (React, TypeScript, Storybook).",
                    "Migrated a legacy jQuery app to React with zero downtime.",
                ],
            },
        ],
        "education": [
            {"degree": "BSc Software Engineering", "school": "Technical University of Berlin", "year": "2019"}
        ],
        "skills": [
            "React", "TypeScript", "Next.js", "Redux", "Tailwind CSS",
            "Jest", "Cypress", "Vite", "Storybook", "accessibility",
        ],
        "languages": ["Russian (native)", "English (fluent)", "German (B2)"],
        "certifications": [],
    },
    {
        "id": "james_okafor",
        "name": "James Okafor",
        "title": "Senior Site Reliability Engineer",
        "email": "james.okafor@example.com",
        "phone": "+234 803 456 7890",
        "location": "Lagos, Nigeria (remote)",
        "layout": "table",
        "summary": "DevOps/SRE with 9 years across sysadmin, platform engineering, and reliability. "
        "Runs Kubernetes in production, automates everything with Terraform, and builds observability people actually use.",
        "experience": [
            {
                "company": "Stackway",
                "role": "Senior SRE",
                "start": "May 2023",
                "end": "Present",
                "bullets": [
                    "Defined SLOs and error budgets for 12 services; on-call incident commander.",
                    "Built the Prometheus/Grafana observability stack used by 40 engineers.",
                ],
            },
            {
                "company": "FinEdge",
                "role": "DevOps Engineer",
                "start": "Feb 2019",
                "end": "Apr 2023",
                "bullets": [
                    "Migrated workloads to Kubernetes (EKS) managed entirely with Terraform.",
                    "Cut deployment time from 45 minutes to 6 via GitHub Actions pipelines.",
                ],
            },
            {
                "company": "CloudNine Hosting",
                "role": "Systems Administrator",
                "start": "Jan 2017",
                "end": "Jan 2019",
                "bullets": [
                    "Managed 200+ Linux servers; wrote Ansible playbooks replacing manual runbooks.",
                ],
            },
        ],
        "education": [
            {"degree": "BSc Computer Engineering", "school": "University of Lagos", "year": "2016"}
        ],
        "skills": [
            "Kubernetes", "Terraform", "AWS", "GCP", "Ansible", "Prometheus",
            "Grafana", "Bash", "Python", "GitHub Actions",
        ],
        "languages": ["English (native)"],
        "certifications": ["CKA (Certified Kubernetes Administrator)", "AWS SysOps Administrator"],
    },
    {
        "id": "layla_nasser",
        "name": "Layla Nasser",
        "title": "Data Scientist",
        "email": "layla.nasser@example.com",
        "phone": "+961 71 456 789",
        "location": "Beirut, Lebanon",
        "layout": "standard",
        "summary": "Data scientist blending statistical rigor with business sense. "
        "Builds churn and propensity models, designs A/B tests, and communicates results to non-technical stakeholders.",
        "experience": [
            {
                "company": "LevantPay",
                "role": "Data Scientist",
                "start": "Mar 2022",
                "end": "Present",
                "bullets": [
                    "Built the churn-prediction model (scikit-learn) saving an estimated $400k/year.",
                    "Designed and analyzed 20+ A/B tests for the growth team.",
                ],
            },
            {
                "company": "RetailIQ",
                "role": "Data Analyst",
                "start": "Jan 2020",
                "end": "Feb 2022",
                "bullets": [
                    "Owned the executive KPI dashboards (SQL, Tableau).",
                    "Automated weekly reporting, saving the analytics team 10 hours/week.",
                ],
            },
        ],
        "education": [
            {"degree": "MSc Statistics", "school": "Saint Joseph University of Beirut", "year": "2019"}
        ],
        "skills": [
            "Python", "pandas", "scikit-learn", "SQL", "Tableau", "Power BI",
            "A/B testing", "statistics", "data storytelling",
        ],
        "languages": ["Arabic (native)", "French (fluent)", "English (fluent)"],
        "certifications": [],
    },
    {
        "id": "marco_rossi",
        "name": "Marco Rossi",
        "title": "Senior Full-Stack Developer",
        "email": "marco.rossi@example.com",
        "phone": "+39 340 567 8901",
        "location": "Milan, Italy",
        "layout": "standard",
        "summary": "Full-stack developer comfortable across the whole product: Node.js and NestJS on the back, "
        "React on the front, PostgreSQL underneath, AWS around it all.",
        "experience": [
            {
                "company": "Lumina",
                "role": "Senior Full-Stack Developer",
                "start": "Feb 2024",
                "end": "Present",
                "bullets": [
                    "Built the invoicing module end-to-end (NestJS, React, PostgreSQL).",
                    "Introduced end-to-end testing with Playwright, catching 30+ regressions pre-release.",
                ],
            },
            {
                "company": "Trenta",
                "role": "Full-Stack Developer",
                "start": "May 2021",
                "end": "Jan 2024",
                "bullets": [
                    "Developed customer-facing features on a Node.js/React/MongoDB stack.",
                    "Improved API response times 3x by adding Redis caching.",
                ],
            },
            {
                "company": "Freelance",
                "role": "Web Developer",
                "start": "Jun 2018",
                "end": "Apr 2021",
                "bullets": [
                    "Delivered 15+ web applications for small businesses across Italy.",
                ],
            },
        ],
        "education": [
            {"degree": "BSc Computer Science", "school": "University of Milan", "year": "2018"}
        ],
        "skills": [
            "JavaScript", "TypeScript", "Node.js", "NestJS", "React",
            "MongoDB", "PostgreSQL", "Redis", "Docker", "AWS",
        ],
        "languages": ["Italian (native)", "English (fluent)", "Spanish (conversational)"],
        "certifications": [],
    },
    {
        "id": "aisha_khan",
        "name": "Aisha Khan",
        "title": "Senior Data Engineer",
        "email": "aisha.khan@example.com",
        "phone": "+92 300 678 9012",
        "location": "Karachi, Pakistan (remote)",
        "layout": "standard",
        "summary": "Data engineer who builds pipelines that don't wake anyone at 3am. "
        "Seven years across ETL, warehousing, and streaming; strong dbt and Airflow practitioner.",
        "experience": [
            {
                "company": "Finlytics",
                "role": "Senior Data Engineer",
                "start": "Mar 2024",
                "end": "Present",
                "bullets": [
                    "Own the dbt/Snowflake warehouse (300+ models) powering company analytics.",
                    "Built Kafka streaming ingestion handling 50k events/second.",
                ],
            },
            {
                "company": "NorthStar Analytics",
                "role": "Data Engineer",
                "start": "Apr 2021",
                "end": "Feb 2024",
                "bullets": [
                    "Orchestrated 80+ Airflow DAGs feeding a Redshift warehouse.",
                    "Rebuilt the core Spark ETL, cutting nightly batch time from 6h to 90min.",
                ],
            },
            {
                "company": "DataBridge",
                "role": "ETL Developer",
                "start": "Jun 2019",
                "end": "Mar 2021",
                "bullets": [
                    "Migrated legacy SSIS packages to Python-based ETL.",
                ],
            },
        ],
        "education": [
            {"degree": "BSc Computer Science", "school": "NED University, Karachi", "year": "2019"}
        ],
        "skills": [
            "Python", "SQL", "Apache Spark", "Airflow", "dbt", "Kafka",
            "Snowflake", "Redshift", "AWS", "data modeling",
        ],
        "languages": ["Urdu (native)", "English (fluent)"],
        "certifications": ["SnowPro Core"],
    },
    {
        "id": "daniel_kim",
        "name": "Daniel Kim",
        "title": "Mobile Developer",
        "email": "daniel.kim@example.com",
        "phone": "+82 10 789 0123",
        "location": "Seoul, South Korea",
        "layout": "standard",
        "summary": "Mobile developer shipping consumer apps since 2019. "
        "Native Android background, now leading cross-platform Flutter development.",
        "experience": [
            {
                "company": "Whistle",
                "role": "Mobile Engineer",
                "start": "Jul 2022",
                "end": "Present",
                "bullets": [
                    "Lead Flutter development for a messaging app with 500k MAU.",
                    "Set up mobile CI/CD with Fastlane; release cycle went from monthly to weekly.",
                ],
            },
            {
                "company": "AppNova",
                "role": "Android Developer",
                "start": "Mar 2019",
                "end": "Jun 2022",
                "bullets": [
                    "Built Kotlin apps totalling 1M+ downloads on Google Play.",
                    "Reduced crash rate from 2.1% to 0.3% through systematic instrumentation.",
                ],
            },
        ],
        "education": [
            {"degree": "BSc Computer Science", "school": "Hanyang University", "year": "2018"}
        ],
        "skills": [
            "Kotlin", "Flutter", "Dart", "Firebase", "REST APIs",
            "GraphQL", "Fastlane", "Swift (basic)",
        ],
        "languages": ["Korean (native)", "English (professional)"],
        "certifications": [],
    },
    {
        "id": "fatima_al_sayed",
        "name": "Fatima Al-Sayed",
        "title": "AI Engineer",
        "email": "fatima.alsayed@example.com",
        "phone": "+962 79 890 1234",
        "location": "Amman, Jordan",
        "layout": "two_column",
        "summary": "AI engineer specializing in LLM applications: retrieval-augmented generation, "
        "vector search, and evaluation. NLP background with production deployments in Arabic and English.",
        "experience": [
            {
                "company": "Maktabi AI",
                "role": "AI Engineer",
                "start": "Jan 2023",
                "end": "Present",
                "bullets": [
                    "Built RAG chatbots over legal documents using LangChain and Qdrant, with inline citations.",
                    "Set up RAGAS-based evaluation, raising retrieval hit-rate from 68% to 91%.",
                    "Deployed LLM services (FastAPI) with Langfuse tracing in production.",
                ],
            },
            {
                "company": "TextLab",
                "role": "NLP Engineer",
                "start": "Feb 2021",
                "end": "Dec 2022",
                "bullets": [
                    "Built Arabic NER pipelines with spaCy and Hugging Face Transformers.",
                    "Fine-tuned BERT-family models for document classification (F1 0.92).",
                ],
            },
        ],
        "education": [
            {"degree": "BSc Computer Science", "school": "University of Jordan", "year": "2020"}
        ],
        "skills": [
            "Python", "LangChain", "LlamaIndex", "RAG", "Qdrant", "pgvector",
            "Hugging Face Transformers", "FastAPI", "prompt engineering", "RAGAS", "spaCy",
        ],
        "languages": ["Arabic (native)", "English (fluent)"],
        "certifications": [],
    },
    {
        "id": "tomas_garcia",
        "name": "Tomas Garcia",
        "title": "Senior QA Automation Engineer",
        "email": "tomas.garcia@example.com",
        "phone": "+54 911 901 2345",
        "location": "Buenos Aires, Argentina (remote)",
        "layout": "standard",
        "summary": "QA engineer who moved from manual testing to full automation ownership. "
        "Builds test frameworks, wires them into CI, and treats flaky tests as bugs.",
        "experience": [
            {
                "company": "GreenCart",
                "role": "Senior QA Automation Engineer",
                "start": "Aug 2023",
                "end": "Present",
                "bullets": [
                    "Own the Cypress + Playwright suites gating every deploy (900+ tests, <1% flake rate).",
                    "Introduced contract testing for 14 internal APIs.",
                ],
            },
            {
                "company": "PagoSur",
                "role": "QA Automation Engineer",
                "start": "Apr 2020",
                "end": "Jul 2023",
                "bullets": [
                    "Built the Selenium-based regression suite for a payments platform.",
                    "Automated API testing with Postman/Newman in CI.",
                ],
            },
            {
                "company": "SoftQA",
                "role": "Manual Tester",
                "start": "Mar 2018",
                "end": "Mar 2020",
                "bullets": [
                    "Executed test plans for web and mobile clients.",
                ],
            },
        ],
        "education": [
            {"degree": "Technical Degree in Programming", "school": "UTN Buenos Aires", "year": "2017"}
        ],
        "skills": [
            "Cypress", "Playwright", "Selenium", "Python", "JavaScript",
            "Postman", "JMeter", "CI/CD", "contract testing",
        ],
        "languages": ["Spanish (native)", "English (fluent)", "Portuguese (conversational)"],
        "certifications": ["ISTQB Foundation"],
    },
    {
        "id": "nour_khalil",
        "name": "Nour Khalil",
        "title": "Junior Software Engineer",
        "email": "nour.khalil@example.com",
        "phone": "+961 76 012 345",
        "location": "Tripoli, Lebanon",
        "layout": "standard",
        "summary": "Recent computer science graduate with internship and one year of professional experience. "
        "Comfortable in Python and Java; eager to grow into backend development.",
        "experience": [
            {
                "company": "LebTech Labs",
                "role": "Junior Software Engineer",
                "start": "Feb 2025",
                "end": "Present",
                "bullets": [
                    "Develop and maintain REST APIs in Python (Flask) for client projects.",
                    "Wrote data-cleaning scripts that automated a weekly manual process.",
                ],
            },
            {
                "company": "CedarSoft",
                "role": "Software Engineering Intern",
                "start": "Jun 2024",
                "end": "Sep 2024",
                "bullets": [
                    "Fixed bugs and wrote unit tests for a Java Spring Boot application.",
                ],
            },
        ],
        "education": [
            {"degree": "BSc Computer Science", "school": "Lebanese University", "year": "2024"}
        ],
        "skills": [
            "Python", "Java", "Flask", "Spring Boot (basic)", "Git", "SQL", "HTML/CSS",
        ],
        "languages": ["Arabic (native)", "English (fluent)", "French (fluent)"],
        "certifications": [],
    },
    {
        "id": "sophie_dubois",
        "name": "Sophie Dubois",
        "title": "Senior Product Manager",
        "email": "sophie.dubois@example.com",
        "phone": "+33 6 12 34 56 78",
        "location": "Paris, France",
        "layout": "standard",
        "summary": "Product manager for technical products, most recently ML-powered features. "
        "Strong on discovery, ruthless prioritization, and working hand-in-hand with engineering.",
        "experience": [
            {
                "company": "Sensei",
                "role": "Senior Product Manager",
                "start": "Jun 2023",
                "end": "Present",
                "bullets": [
                    "Own the roadmap for ML-powered document processing (OCR + extraction).",
                    "Shipped 3 major features that grew ARR by 25%.",
                ],
            },
            {
                "company": "Movado",
                "role": "Product Manager",
                "start": "Sep 2019",
                "end": "May 2023",
                "bullets": [
                    "Led payments and checkout products for a marketplace with 2M users.",
                    "Ran continuous discovery; 40+ user interviews per quarter.",
                ],
            },
            {
                "company": "Yello",
                "role": "Business Analyst",
                "start": "Sep 2017",
                "end": "Aug 2019",
                "bullets": [
                    "Analyzed funnel data (SQL) and defined KPIs for the product org.",
                ],
            },
        ],
        "education": [
            {"degree": "MSc Management", "school": "HEC Paris", "year": "2017"}
        ],
        "skills": [
            "product discovery", "roadmapping", "SQL", "agile/Scrum", "Jira",
            "A/B testing", "stakeholder management", "Figma (basic)",
        ],
        "languages": ["French (native)", "English (fluent)"],
        "certifications": [],
    },
    {
        "id": "viktor_ivanov",
        "name": "Viktor Ivanov",
        "title": "Security Engineer",
        "email": "viktor.ivanov@example.com",
        "phone": "+359 88 123 4567",
        "location": "Sofia, Bulgaria",
        "layout": "standard",
        "summary": "Security engineer covering offense and defense: penetration testing, cloud security "
        "reviews, and incident response. Started in the SOC, still thinks like an attacker.",
        "experience": [
            {
                "company": "BlueShield",
                "role": "Security Engineer",
                "start": "May 2021",
                "end": "Present",
                "bullets": [
                    "Perform web application penetration tests for enterprise clients (OWASP methodology).",
                    "Led AWS security reviews; found and remediated 3 critical misconfigurations.",
                    "Incident responder for ransomware and phishing cases.",
                ],
            },
            {
                "company": "SecOps Ltd",
                "role": "SOC Analyst",
                "start": "Jun 2018",
                "end": "Apr 2021",
                "bullets": [
                    "Triaged alerts in Splunk SIEM for 30+ enterprise customers.",
                    "Wrote Python automations reducing false-positive triage time by half.",
                ],
            },
        ],
        "education": [
            {"degree": "BSc Informatics", "school": "Sofia University", "year": "2018"}
        ],
        "skills": [
            "penetration testing", "Burp Suite", "Splunk", "Python",
            "network security", "AWS security", "OWASP", "incident response",
        ],
        "languages": ["Bulgarian (native)", "English (fluent)"],
        "certifications": ["OSCP", "CompTIA Security+"],
    },
    {
        "id": "grace_wanjiru",
        "name": "Grace Wanjiru",
        "title": "Principal Cloud Architect",
        "email": "grace.wanjiru@example.com",
        "phone": "+254 722 234 567",
        "location": "Nairobi, Kenya",
        "layout": "standard",
        "summary": "Cloud architect with 13 years from systems engineering to principal-level architecture. "
        "Designs multi-cloud platforms, leads large migrations, and keeps the bill under control.",
        "experience": [
            {
                "company": "Zindua",
                "role": "Principal Cloud Architect",
                "start": "Oct 2021",
                "end": "Present",
                "bullets": [
                    "Architected the multi-cloud platform (AWS + GCP) for a pan-African fintech.",
                    "Led a 30-person cloud migration program, completed 2 months early.",
                    "Cut annual cloud spend 35% via rightsizing and savings plans.",
                ],
            },
            {
                "company": "CloudPath",
                "role": "Cloud Engineer",
                "start": "Mar 2017",
                "end": "Sep 2021",
                "bullets": [
                    "Executed 12 datacenter-to-AWS migrations for enterprise clients.",
                    "Standardized infrastructure-as-code with Terraform across all projects.",
                ],
            },
            {
                "company": "TelcoOne",
                "role": "Systems Engineer",
                "start": "Jan 2013",
                "end": "Feb 2017",
                "bullets": [
                    "Ran core Linux/VMware infrastructure for a national telco.",
                ],
            },
        ],
        "education": [
            {"degree": "BSc Information Technology", "school": "University of Nairobi", "year": "2012"}
        ],
        "skills": [
            "AWS", "GCP", "Azure", "Terraform", "Kubernetes", "networking",
            "serverless", "cost optimization", "architecture reviews",
        ],
        "languages": ["Swahili (native)", "English (fluent)"],
        "certifications": ["AWS Solutions Architect - Professional", "GCP Professional Cloud Architect"],
    },
    {
        "id": "hassan_fares",
        "name": "Hassan Fares",
        "title": "Backend Engineer (Go)",
        "email": "hassan.fares@example.com",
        "phone": "+961 3 345 678",
        "location": "Beirut, Lebanon (remote)",
        "layout": "standard",
        "summary": "Backend engineer working in Go on high-throughput systems. "
        "Payments and streaming background; obsessive about latency budgets and clean interfaces.",
        "experience": [
            {
                "company": "Paylink",
                "role": "Backend Engineer",
                "start": "Jun 2023",
                "end": "Present",
                "bullets": [
                    "Build payment-processing services in Go handling 3k transactions/second.",
                    "Designed the idempotency layer eliminating duplicate-charge incidents.",
                ],
            },
            {
                "company": "StreamCast",
                "role": "Backend Developer",
                "start": "Jan 2020",
                "end": "May 2023",
                "bullets": [
                    "Built Go microservices (gRPC) for a music-streaming platform.",
                    "Implemented playlist sync used by 800k daily listeners.",
                ],
            },
        ],
        "education": [
            {"degree": "BSc Computer Science", "school": "Lebanese American University", "year": "2019"}
        ],
        "skills": [
            "Go", "gRPC", "PostgreSQL", "Redis", "Docker", "Kubernetes",
            "RabbitMQ", "microservices",
        ],
        "languages": ["Arabic (native)", "English (fluent)"],
        "certifications": [],
    },
    {
        "id": "mia_johansson",
        "name": "Mia Johansson",
        "title": "Product Designer",
        "email": "mia.johansson@example.com",
        "phone": "+46 70 456 7890",
        "location": "Stockholm, Sweden",
        "layout": "standard",
        "summary": "Product designer covering research through polished UI. "
        "Builds design systems, runs usability studies, and partners closely with engineers.",
        "experience": [
            {
                "company": "Klippa",
                "role": "Product Designer",
                "start": "Aug 2022",
                "end": "Present",
                "bullets": [
                    "Own the design system used across 4 product teams.",
                    "Ran 30+ usability sessions informing the app redesign that lifted retention 8%.",
                ],
            },
            {
                "company": "Designly",
                "role": "UI Designer",
                "start": "May 2019",
                "end": "Jul 2022",
                "bullets": [
                    "Designed marketing sites and app UIs for 20+ agency clients.",
                ],
            },
        ],
        "education": [
            {"degree": "BA Interaction Design", "school": "Umea Institute of Design", "year": "2018"}
        ],
        "skills": [
            "Figma", "user research", "prototyping", "design systems",
            "accessibility", "usability testing", "HTML/CSS (basic)",
        ],
        "languages": ["Swedish (native)", "English (fluent)"],
        "certifications": [],
    },
]

# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------

ACCENT = colors.HexColor("#1a4d7c")


def make_styles():
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle("name", parent=base["Title"], fontSize=20, spaceAfter=2, textColor=ACCENT),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontSize=11, textColor=colors.HexColor("#444444"), spaceAfter=2),
        "contact": ParagraphStyle("contact", parent=base["Normal"], fontSize=9, textColor=colors.HexColor("#666666"), spaceAfter=8),
        "section": ParagraphStyle("section", parent=base["Heading2"], fontSize=12, textColor=ACCENT, spaceBefore=10, spaceAfter=4),
        "job": ParagraphStyle("job", parent=base["Normal"], fontSize=10.5, spaceBefore=6, spaceAfter=2),
        "body": ParagraphStyle("body", parent=base["Normal"], fontSize=10, leading=13),
        "bullet": ParagraphStyle("bullet", parent=base["Normal"], fontSize=10, leading=13, leftIndent=14, bulletIndent=4),
    }


def section_header(text, styles):
    return [
        Paragraph(text, styles["section"]),
        HRFlowable(width="100%", thickness=0.7, color=ACCENT, spaceAfter=4),
    ]


def experience_flowables(profile, styles):
    out = []
    for job in profile["experience"]:
        out.append(
            Paragraph(
                f"<b>{job['role']}</b> — {job['company']} &nbsp;&nbsp;<i>({job['start']} – {job['end']})</i>",
                styles["job"],
            )
        )
        for b in job["bullets"]:
            out.append(Paragraph(b, styles["bullet"], bulletText="•"))
    return out


def common_tail(profile, styles):
    """Education / Skills / Languages / Certifications sections."""
    out = []
    out += section_header("Education", styles)
    for edu in profile["education"]:
        out.append(Paragraph(f"<b>{edu['degree']}</b>, {edu['school']} ({edu['year']})", styles["body"]))
    out += section_header("Skills", styles)
    out.append(Paragraph(", ".join(profile["skills"]), styles["body"]))
    out += section_header("Languages", styles)
    out.append(Paragraph(" · ".join(profile["languages"]), styles["body"]))
    if profile["certifications"]:
        out += section_header("Certifications", styles)
        for cert in profile["certifications"]:
            out.append(Paragraph(cert, styles["bullet"], bulletText="•"))
    return out


def header_flowables(profile, styles):
    return [
        Paragraph(profile["name"], styles["name"]),
        Paragraph(f"{profile['title']} — {profile['location']}", styles["subtitle"]),
        Paragraph(f"{profile['email']} | {profile['phone']}", styles["contact"]),
    ]


def render_standard(profile, path):
    doc = SimpleDocTemplate(str(path), pagesize=letter, topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    styles = make_styles()
    story = header_flowables(profile, styles)
    story += section_header("Summary", styles)
    story.append(Paragraph(profile["summary"], styles["body"]))
    story += section_header("Experience", styles)
    story += experience_flowables(profile, styles)
    story += common_tail(profile, styles)
    doc.build(story)


def render_two_column(profile, path):
    """Awkward layout #1: narrow sidebar (contact/skills/languages) + main column."""
    doc = SimpleDocTemplate(str(path), pagesize=letter, topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    styles = make_styles()

    left = [Paragraph("Contact", styles["section"]), Paragraph(profile["email"], styles["body"]),
            Paragraph(profile["phone"], styles["body"]), Paragraph(profile["location"], styles["body"]),
            Spacer(1, 8), Paragraph("Skills", styles["section"])]
    for skill in profile["skills"]:
        left.append(Paragraph(skill, styles["bullet"], bulletText="•"))
    left += [Spacer(1, 8), Paragraph("Languages", styles["section"])]
    for lang in profile["languages"]:
        left.append(Paragraph(lang, styles["bullet"], bulletText="•"))

    right = [Paragraph("Profile", styles["section"]), Paragraph(profile["summary"], styles["body"]),
             Paragraph("Experience", styles["section"])]
    right += experience_flowables(profile, styles)
    right.append(Paragraph("Education", styles["section"]))
    for edu in profile["education"]:
        right.append(Paragraph(f"<b>{edu['degree']}</b>, {edu['school']} ({edu['year']})", styles["body"]))

    story = [
        Paragraph(profile["name"], styles["name"]),
        Paragraph(profile["title"], styles["subtitle"]),
        Spacer(1, 6),
        Table(
            [[left, right]],
            colWidths=[1.9 * inch, 4.9 * inch],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#eef3f8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ]),
        ),
    ]
    doc.build(story)


def render_table_experience(profile, path):
    """Awkward layout #2: experience rendered as a bordered table."""
    doc = SimpleDocTemplate(str(path), pagesize=letter, topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    styles = make_styles()
    story = header_flowables(profile, styles)
    story += section_header("Summary", styles)
    story.append(Paragraph(profile["summary"], styles["body"]))
    story += section_header("Experience", styles)

    rows = [[Paragraph("<b>Period</b>", styles["body"]),
             Paragraph("<b>Company / Role</b>", styles["body"]),
             Paragraph("<b>Highlights</b>", styles["body"])]]
    for job in profile["experience"]:
        rows.append([
            Paragraph(f"{job['start']} – {job['end']}", styles["body"]),
            Paragraph(f"<b>{job['company']}</b><br/>{job['role']}", styles["body"]),
            Paragraph("<br/>".join(f"• {b}" for b in job["bullets"]), styles["body"]),
        ])
    story.append(Table(
        rows,
        colWidths=[1.2 * inch, 1.7 * inch, 3.9 * inch],
        style=TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3f8")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]),
    ))
    story += common_tail(profile, styles)
    doc.build(story)


RENDERERS = {
    "standard": render_standard,
    "two_column": render_two_column,
    "table": render_table_experience,
}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for profile in PROFILES:
        path = OUT_DIR / f"{profile['id']}.pdf"
        RENDERERS[profile["layout"]](profile, path)
        print(f"  wrote {path.name}  ({profile['layout']})")
    GROUND_TRUTH.write_text(json.dumps(PROFILES, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(PROFILES)} CVs -> {OUT_DIR}")
    print(f"ground truth -> {GROUND_TRUTH}")


if __name__ == "__main__":
    main()
