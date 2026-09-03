from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.lib.units import inch
from datetime import datetime
import json
import re
from reportlab.pdfgen import canvas

def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.grey)

    page_num = canvas.getPageNumber()

    canvas.drawRightString(
        570,
        20,
        f"Page {page_num}"
    )

    canvas.restoreState()
    
    
# ===============================
# Helper Functions
# ===============================


def clean_issue_text(issue):

    """
    Remove temp file path from analyzer output
    """

    if ":" in issue:

        parts = issue.split(":", 3)

        if len(parts) >= 4:
            return parts[3].strip()


    return issue



def get_grade(score):

    if score >= 80:
        return "A"

    elif score >= 60:
        return "B"

    elif score >= 40:
        return "C"

    elif score >= 20:
        return "D"

    else:
        return "F"



def create_styles():

    styles = getSampleStyleSheet()

    return {

        "title":
        ParagraphStyle(
            "title",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontSize=22,
            textColor=colors.HexColor("#495B16"),   # TestPilot olive
            spaceAfter=15
        ),

        "heading":
        ParagraphStyle(
            "heading",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=colors.HexColor("#495B16"),   # TestPilot olive
            spaceBefore=8,
            spaceAfter=6
        ),

        "normal":
        ParagraphStyle(
            "normal",
            parent=styles["BodyText"],
            fontSize=10,
            leading=16,
            textColor=colors.HexColor("#333333")
        )

    }


# ===============================
# PDF Generator
# ===============================


def generate_code_pdf(
    data,
    filename="code_analysis_report.pdf"
):


    doc = SimpleDocTemplate(
        filename
    )


    styles = create_styles()


    title = styles["title"]

    heading = styles["heading"]

    normal = styles["normal"]



    story = []



    # ---------------------------
    # Load Data
    # ---------------------------


    analysis = data.get(
        "analysis",
        {}
    )


    security = data.get(
        "security_analysis",
        {}
    )



    if isinstance(
        analysis,
        str
    ):

        analysis = json.loads(
            analysis
        )



    if isinstance(
        security,
        str
    ):

        security = json.loads(
            security
        )



    score = analysis.get(
        "score",
        0
    )


    security_score = security.get(
        "score",
        0
    )




    # ---------------------------
    # Header
    # ---------------------------


    header = Table(

        [

            [

                Paragraph(

                    "<b>TestPilot</b><br/>"
                    "Code Analysis Report",

                    title

                )

            ]

        ],

        colWidths=[
            450
        ]

    )


    header.setStyle(

        TableStyle(

            [

                (
                    "BACKGROUND",
                    (0,0),
                    (-1,-1),
                    colors.HexColor("#EAF2F8")
                ),


                (
                    "BOX",
                    (0,0),
                    (-1,-1),
                    1,
                    colors.HexColor("#1F4E79")
                ),


                (
                    "ALIGN",
                    (0,0),
                    (-1,-1),
                    "CENTER"
                )

            ]

        )

    )



    story.append(
        header
    )


    story.append(
        Spacer(
            1,
            0.3*inch
        )
    )




    # ---------------------------
    # File Details
    # ---------------------------


    story.append(

        Paragraph(

            f"""
            <b>File Name :</b> {data.get('filename','')}<br/>
            <b>Language :</b> {data.get('language','')}<br/>
            <b>Generated :</b>
            {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
            """,

            normal

        )

    )



    story.append(
        Spacer(
            1,
            0.3*inch
        )
    )




    # ---------------------------
    # Score Dashboard
    # ---------------------------


    score_table = Table(

        [

            [

                "Code Quality",

                "Security",

                "Grade"

            ],


            [

                f"{score}/100",

                f"{security_score}/100",

                get_grade(score)

            ]

        ],

        colWidths=[
            150,
            150,
            150
        ]

    )



    score_table.setStyle(

        TableStyle(

            [

                (
                    "BACKGROUND",
                    (0,0),
                    (-1,0),
                    colors.HexColor("#1F4E79")
                ),


                (
                    "TEXTCOLOR",
                    (0,0),
                    (-1,0),
                    colors.white
                ),


                (
                    "GRID",
                    (0,0),
                    (-1,-1),
                    1,
                    colors.grey
                ),


                (
                    "ALIGN",
                    (0,0),
                    (-1,-1),
                    "CENTER"
                )

            ]

        )

    )



    story.append(
        score_table
    )


    story.append(
        Spacer(
            1,
            0.4*inch
        )
    )
        # ===========================
    # Detected Issues
    # ===========================


    story.append(
        Paragraph(
            "Detected Code Issues",
            heading
        )
    )


    issues = analysis.get(
        "issues",
        []
    )


    if isinstance(
        issues,
        str
    ):

        try:
            issues = json.loads(
                issues
            )

        except:

            issues = [
                issues
            ]



    if not issues:


        story.append(

            Paragraph(
                "No issues detected.",
                normal
            )

        )


    else:


        issue_table = [

            [
                "#",
                "Issue Description"
            ]

        ]



        for index, issue in enumerate(
            issues,
            start=1
        ):


            cleaned = clean_issue_text(
                issue
            )


            issue_table.append(

                [

                    str(index),

                    cleaned

                ]

            )




        issue_tbl = Table(

            issue_table,

            colWidths=[
                40,
                380
            ]

        )



        issue_tbl.setStyle(

            TableStyle(

                [

                    (
                        "BACKGROUND",
                        (0,0),
                        (-1,0),
                        colors.HexColor("#1F4E79")
                    ),


                    (
                        "TEXTCOLOR",
                        (0,0),
                        (-1,0),
                        colors.white
                    ),


                    (
                        "GRID",
                        (0,0),
                        (-1,-1),
                        0.5,
                        colors.grey
                    ),


                    (
                        "VALIGN",
                        (0,0),
                        (-1,-1),
                        "TOP"
                    )

                ]

            )

        )



        story.append(
            issue_tbl
        )



    story.append(

        Spacer(
            1,
            0.35*inch
        )

    )





    # ===========================
    # Security Analysis
    # ===========================


    story.append(

        Paragraph(
            "Security Analysis",
            heading
        )

    )



    security_issues = security.get(
        "issues",
        []
    )



    if not security_issues:


        story.append(

            Paragraph(
                "No security issues detected.",
                normal
            )

        )


    else:


        for item in security_issues:


            story.append(

                Paragraph(
                    f"• {item}",
                    normal
                )

            )



    story.append(

        Spacer(
            1,
            0.35*inch
        )

    )





    # ===========================
    # Severity Summary
    # ===========================


    story.append(

        Paragraph(
            "Severity Summary",
            heading
        )

    )



    severity = data.get(
        "severity",
        {}
    )



    if isinstance(
        severity,
        str
    ):

        try:

            severity = json.loads(
                severity
            )

        except:

            severity = {}




    severity_table = [

        [
            "Level",
            "Count"
        ],


        [
            "Critical",
            severity.get(
                "critical",
                0
            )
        ],


        [
            "High",
            severity.get(
                "high",
                0
            )
        ],


        [
            "Medium",
            severity.get(
                "medium",
                0
            )
        ],


        [
            "Low",
            severity.get(
                "low",
                0
            )
        ]

    ]




    sev_table = Table(

        severity_table,

        colWidths=[
            200,
            100
        ]

    )



    sev_table.setStyle(

        TableStyle(

            [

                (
                    "BACKGROUND",
                    (0,0),
                    (-1,0),
                    colors.HexColor("#1F4E79")
                ),


                (
                    "TEXTCOLOR",
                    (0,0),
                    (-1,0),
                    colors.white
                ),


                (
                    "GRID",
                    (0,0),
                    (-1,-1),
                    0.5,
                    colors.grey
                ),


                (
                    "ALIGN",
                    (1,1),
                    (-1,-1),
                    "CENTER"
                )

            ]

        )

    )


    story.append(
        sev_table
    )



    story.append(

        Spacer(
            1,
            0.35*inch
        )

    )
        # ===========================
    # AI Suggestions
    # ===========================


    story.append(

        Paragraph(
            "AI Code Review Suggestions",
            heading
        )

    )



    ai = data.get(
        "ai_suggestions",
        ""
    )



    if isinstance(ai, dict):

        ai_json = ai


    else:

        try:

            ai = str(ai)

            ai = re.sub(
                r"```json|```",
                "",
                ai
            ).strip()


            ai_json = json.loads(
                ai
            )


        except:


            ai_json = {}





    # Handle double encoded JSON

    if isinstance(ai_json, str):

        try:

            ai_json = json.loads(ai_json)

        except:

            ai_json = {
                "AI Review": ai_json
            }



    if ai_json:


        for key, value in ai_json.items():


            story.append(

                Paragraph(
                    f"<b>{key}</b>",
                    normal
                )

            )



            if isinstance(
                value,
                list
            ):


                for index, item in enumerate(
                    value,
                    start=1
                ):


                    story.append(

                        Paragraph(

                            f"{index}. {item}",

                            normal

                        )

                    )



            else:


                story.append(

                    Paragraph(

                        str(value),

                        normal

                    )

                )



            story.append(

                Spacer(
                    1,
                    0.12*inch
                )

            )



    else:


        story.append(

            Paragraph(

                "No AI suggestions available.",

                normal

            )

        )





    story.append(

        Spacer(
            1,
            0.4*inch
        )

    )





    # ===========================
    # Developer Improvement Summary
    # ===========================


    story.append(

        Paragraph(
            "Recommended Improvements",
            heading
        )

    )


    improvements = [

        "Fix code quality issues reported by analyzer.",

        "Remove unused imports and variables.",

        "Add proper documentation and function docstrings.",

        "Improve security by removing hardcoded credentials.",

        "Follow coding standards and best practices."

    ]



    for index, item in enumerate(
        improvements,
        start=1
    ):


        story.append(

            Paragraph(

                f"{index}. {item}",

                normal

            )

        )




    story.append(

        Spacer(
            1,
            0.5*inch
        )

    )





    # ===========================
    # Footer
    # ===========================


    footer = Table(
    [
    [
    "Generated by TestPilot | Version 1.0 | Confidential"
    ]
    ],
    colWidths=[450]
    )



    footer.setStyle(

        TableStyle(

            [

                (
                    "BACKGROUND",
                    (0,0),
                    (-1,-1),
                    colors.HexColor("#1F4E79")
                ),


                (
                    "TEXTCOLOR",
                    (0,0),
                    (-1,-1),
                    colors.white
                ),


                (
                    "ALIGN",
                    (0,0),
                    (-1,-1),
                    "CENTER"
                ),


                (
                    "TOPPADDING",
                    (0,0),
                    (-1,-1),
                    10
                ),


                (
                    "BOTTOMPADDING",
                    (0,0),
                    (-1,-1),
                    10
                )

            ]

        )

    )



    story.append(
        footer
    )




    # Build PDF

    doc.build(
        story
    )


    return filename

def generate_pdf_report(
    data,
    filename="Website_Report.pdf"
):
    print("========== PDF SEO ==========")
    print(data.get("seo"))
    doc = SimpleDocTemplate(filename)

    styles = create_styles()

    title = styles["title"]
    heading = styles["heading"]
    normal = styles["normal"]

    story = []

    website = data.get("website", {})
    seo = data.get("seo", {}) 
    performance = data.get("performance", {})
    accessibility = data.get("accessibility", {})
    broken = data.get("broken_links", {})
    security = data.get("security", {})

    health_score = website.get("health_score", 0)
    seo_score = seo.get("seo_score", 0)
    performance_score = performance.get("performance_score", 0)
    accessibility_score = accessibility.get("accessibility_score", 0)
    
    print("========== PDF SEO ==========")
    print(data.get("seo"))

    # ==========================
    # Header
    # ==========================

    header = Table(
        [[
            Paragraph(
                "<b>TestPilot</b><br/>"
                "Professional Website Testing Report",
                title
            )
        ]],
        colWidths=[450]
    )

    header.setStyle(
        TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#EAF2F8")),
            ("BOX",(0,0),(-1,-1),1,colors.HexColor("#1F4E79")),
            ("ALIGN",(0,0),(-1,-1),"CENTER")
        ])
    )

    story.append(header)
    story.append(Spacer(1,0.30*inch))
    story.append(Paragraph("Executive Summary", heading))

    
    if health_score >= 90:
        status = "🟢 Excellent"

    elif health_score >= 75:
        status = "🟡 Good"

    elif health_score >= 60:
        status = "🟠 Needs Improvement"

    else:
        status = "🔴 Critical"
        
    story.append(
        Paragraph(
            f"""
            This report evaluates the website using automated testing across
            Website Health, SEO, Accessibility, Performance,
            Security and Broken Link Analysis.

            <br/><br/>

            <b>Website Health :</b> {health_score}/100<br/>
            <b>SEO Score :</b> {seo_score}/100<br/>
            <b>Performance Score :</b> {performance_score}/100<br/>
            <b>Accessibility Score :</b> {accessibility_score}/100<br/><br/>

            <b>Overall Status :</b> {status}
            """,
            normal
        )
    )

    story.append(Spacer(1,0.25*inch))

    # ==========================
    # Website Details
    # ==========================

    story.append(
        Paragraph(
            f"""
            <b>Website URL :</b> {data.get('url','')}<br/>
            <b>Generated :</b>
            {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
            """,
            normal
        )
    )

    story.append(Spacer(1,0.30*inch))

    # ==========================
    # Score Dashboard
    # ==========================

    score_table = Table(
        [
            [
                "Health",
                "SEO",
                "Performance",
                "Accessibility"
            ],
            [
                f"{health_score}/100",
                f"{seo_score}/100",
                f"{performance_score}/100",
                f"{accessibility_score}/100"
            ]
        ],
        colWidths=[110,110,110,110]
    )

    score_table.setStyle(
        TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1F4E79")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("GRID",(0,0),(-1,-1),1,colors.grey),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("BACKGROUND",(0,1),(-1,-1),colors.whitesmoke)
        ])
    )

    story.append(score_table)

    story.append(Spacer(1,0.35*inch))
    
    story.append(Paragraph("Website Status", heading))

    status_table = Table(
    [
    ["Status Code", website.get("status_code",0)],
    ["Response Time", f"{website.get('response_time',0)} sec"],
    ["SSL Status", website.get("ssl_status","Unknown")],
    ["Test Status", website.get("test_status","Unknown")],
    ["Health Score", f"{health_score}/100"]
    ],
    colWidths=[200,200]
    )

    status_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#D6EAF8")),
            ("GRID", (0,0), (-1,-1), 1, colors.grey),
            ("BACKGROUND", (0,0), (0,-1), colors.whitesmoke),
            ("ALIGN", (1,0), (-1,-1), "CENTER")
        ])
    )

    story.append(status_table)
    story.append(Spacer(1,0.30*inch))
    story.append(Paragraph("Broken Links Analysis", heading))

    story.append(
        Paragraph(
            f"<b>Total Broken Links:</b> {broken.get('broken_links',0)}",
            normal
        )
    )

    story.append(Spacer(1,0.15*inch))

    if broken.get("broken_links",0) == 0:

        story.append(
            Paragraph(
                "✅ No broken links detected.",
                normal
            )
        )

    else:

        for link in broken.get("links",[]):

            story.append(
                Paragraph(
                    f"❌ {link}",
                    normal
                )
            )

    story.append(Spacer(1,0.30*inch))

    story.append(Spacer(1,0.30*inch))
    story.append(Paragraph("Advanced SEO Analysis", heading))

    seo_table = Table(
    [
        ["SEO Score", f"{seo.get('seo_score',0)}/100"],
        ["Robots.txt", "Available" if seo.get("robots_txt") else "Missing"],
        ["Sitemap.xml", "Available" if seo.get("sitemap_xml") else "Missing"],
        ["Robots Declares Sitemap", "Yes" if seo.get("robots_has_sitemap") else "No"],
        ["Google Analytics", "Installed" if seo.get("google_analytics") else "Missing"],
        ["Google Tag Manager", "Installed" if seo.get("google_tag_manager") else "Missing"],
        ["Mobile Friendly", "Yes" if seo.get("mobile_friendly") else "No"],
        ["Language Tag", seo.get("language","Not Found")],
        ["Title Length", seo.get("title_length",0)],
        ["Meta Description Length", seo.get("description_length",0)],
        ["Canonical Tag", "Available" if seo.get("canonical") else "Missing"],
        ["Favicon", "Available" if seo.get("favicon") else "Missing"],
        ["Twitter Card", "Available" if seo.get("twitter_card") else "Missing"],
        ["Structured Data", "Available" if seo.get("structured_data") else "Missing"],
        ["H1 Count", seo.get("h1_count",0)],
        ["H2 Count", seo.get("h2_count",0)],
        ["Total Images", seo.get("image_seo",{}).get("total_images",0)],
        ["Missing ALT", seo.get("image_seo",{}).get("missing_alt",0)],
        ["Lazy Loaded Images", seo.get("image_seo",{}).get("lazy_loaded",0)],
    ]
    )

    seo_table.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#D6EAF8")),
    ("GRID",(0,0),(-1,-1),1,colors.grey),
    ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
    ("ALIGN",(1,0),(-1,-1),"CENTER")
    ]))

    story.append(seo_table)

    story.append(Spacer(1,0.3*inch))

    story.append(Paragraph("Open Graph", heading))

    og = seo.get("open_graph", {})

    if og is None:
        og = {}

    # If Open Graph comes as JSON string, convert it
    if isinstance(og, str):
        try:
            og = json.loads(og)
        except:
            og = {}

        if og is None:
            og = {}

    story.append(
    Paragraph(
    f"""
    <b>Open Graph</b><br/>
    • Title : {"Yes" if og.get("title", False) else "No"}<br/>
    • Description : {"Yes" if og.get("description", False) else "No"}<br/>
    • Image : {"Yes" if og.get("image", False) else "No"}<br/>
    • URL : {"Yes" if og.get("url", False) else "No"}<br/>
    • Type : {"Yes" if og.get("type", False) else "No"}
    """,
    normal
    )
    )

    story.append(Spacer(1,0.25*inch))
    story.append(Paragraph("Structured Data", heading))

    schemas = seo.get("schema_types", [])

    if schemas:

        for item in schemas:

            story.append(
                Paragraph(
                    f"• {item}",
                    normal
                )
            )

    else:

        story.append(
            Paragraph(
                "No Structured Data Found",
                normal
            )
        )

    story.append(Spacer(1,0.25*inch))
    story.append(Paragraph("Heading Analysis", heading))

    h1 = seo.get("h1_text", [])

    if h1:

        for item in h1:

            story.append(
                Paragraph(
                    f"• {item}",
                    normal
                )
            )

    else:

        story.append(
            Paragraph(
                "No H1 Heading Found",
                normal
            )
        )

    story.append(Spacer(1,0.25*inch))
        # ==========================
    # Accessibility
    # ==========================

    story.append(Paragraph("Accessibility Analysis", heading))

    accessibility_issues = accessibility.get("issues", [])

    if not accessibility_issues:

        story.append(
            Paragraph(
                "No accessibility issues found.",
                normal
            )
        )

    else:

        for item in accessibility_issues:

            story.append(
                Paragraph(
                    f"• {item}",
                    normal
                )
            )

    story.append(Spacer(1,0.30*inch))
    
    # ==========================
    # Performance
    # ==========================

    story.append(Paragraph("Performance Analysis", heading))

    performance_issues = performance.get("issues", [])

    if not performance_issues:

        story.append(
            Paragraph(
                "No performance issues found.",
                normal
            )
        )

    else:

        for item in performance_issues:

            story.append(
                Paragraph(
                    f"• {item}",
                    normal
                )
            )

    story.append(Spacer(1,0.30*inch))
    
    # ==========================
    # Security
    # ==========================

    story.append(Paragraph("Security Analysis", heading))

    security_issues = security.get("issues", [])

    story.append(
    Paragraph(
        f"<b>Security Score :</b> {security.get('security_score',100)}/100",
        normal
    )
)

    story.append(Spacer(1,0.1*inch))

    if not security_issues:

        story.append(
            Paragraph(
                "✅ No critical security issues found.",
                normal
            )
        )

    else:

        for item in security_issues:

            story.append(
                Paragraph(
                    f"• {item}",
                    normal
                )
            )

    story.append(Spacer(1,0.30*inch))
    
    # ==========================
    # AI Suggestions
    # ==========================

    story.append(
        Paragraph(
            "AI Recommendations",
            heading
        )
    )

    ai = data.get("ai_suggestions", "")

    if isinstance(ai, str):

        try:

            ai = re.sub(r"```json|```", "", ai).strip()

            ai_json = json.loads(ai)

        except:

            ai_json = {"Recommendation": ai}

    else:

        ai_json = ai


    for key, value in ai_json.items():

        story.append(
            Paragraph(
                f"<b>{key}</b>",
                heading
            )
        )

        if isinstance(value, list):

            for item in value:

                story.append(
                    Paragraph(
                        f"• {item}",
                        normal
                    )
                )

        else:

            story.append(
                Paragraph(
                    str(value),
                    normal
                )
            )

        story.append(
            Spacer(
                1,
                0.12 * inch
            )
        )

    story.append(
        Spacer(
            1,
            0.35 * inch
        )
    )
    
    footer = Table(
    [
        [
            "Generated by TestPilot | Version 1.0 | Confidential"
        ]
    ],
    colWidths=[450]
)

    footer.setStyle(
        TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#1F4E79")),
            ("TEXTCOLOR",(0,0),(-1,-1),colors.white),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),
            ("TOPPADDING",(0,0),(-1,-1),10),
            ("BOTTOMPADDING",(0,0),(-1,-1),10)
        ]) 
    )

    story.append(footer)
    
    doc.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number
    )

    return filename