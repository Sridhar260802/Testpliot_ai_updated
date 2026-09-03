from unittest import result
from playwright.sync_api import TimeoutError
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin
import os
import time
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)
from reportlab.lib.units import mm
from pathlib import Path

import requests
import re
from collections import Counter

# =====================================
# Global Timeout Settings
# =====================================

DEFAULT_NAV_TIMEOUT = 60000
DEFAULT_ACTION_TIMEOUT = 15000
NETWORK_IDLE_TIMEOUT = 8000
REQUEST_TIMEOUT = 10000


def safe_network_idle(page, timeout=NETWORK_IDLE_TIMEOUT):
    """
    FIX: wait_for_load_state("networkidle") used to have Playwright's
    default 30000ms timeout with NO guard. Real sites rarely go fully
    idle (analytics/chat widgets/websockets keep polling), so it kept
    randomly timing out and failing whole modules that were actually
    fine. This wrapper waits a short, sane amount of time and simply
    continues instead of blowing up the module if idle is never reached.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except TimeoutError:
        print("⚠️ Network did not go fully idle in time - continuing anyway.")
    except Exception as e:
        print(f"⚠️ wait_for_load_state ignored error: {e}")


def safe_goto(page, url, timeout=DEFAULT_NAV_TIMEOUT):
    """Defensive page.goto with one retry on timeout."""
    try:
        return page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    except TimeoutError:
        print(f"⚠️ Navigation timeout for {url}, retrying once...")
        try:
            return page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except Exception as e:
            print(f"❌ Navigation failed again: {e}")
            return None




# =====================================
# Default Credentials
# =====================================

TEST_EMAIL = os.getenv("TEST_EMAIL", "test@example.com")
TEST_PASSWORD = os.getenv("TEST_PASSWORD", "Password123!")

# =====================================
# Screenshot Folder
# =====================================

SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


# =====================================
# Screenshot Helper
# =====================================

def save_screenshot(page, filename):
    path = os.path.join(SCREENSHOT_DIR, filename)

    try:
        page.screenshot(
            path=path,
            full_page=True
        )
    except:
        pass

    return path


# =====================================
# Default Result
# =====================================

def create_result(module_name):

    return {
        "module": module_name,
        "status": "PASS",
        "page_load_time": 0,
        "performance": "",
        "issue": "",
        "possible_reason": "",
        "recommendation": "",
        "developer_action": "",
        "screenshot": ""
    }


# =====================================
# Module 1
# Website Opens
# =====================================

def website_open_test(page, url):

    result = create_result("Website Opens")

    try:

        print(f"\nLoading Website : {url}")

        start_time = time.time()

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        # React / NextJS Hydration
        page.wait_for_timeout(5000)

        safe_network_idle(page)

        load_time = round(
            time.time() - start_time,
            2
        )

        result["page_load_time"] = load_time

        print(f"Load Time : {load_time} sec")

        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(3000)

        if response is None:

            result["status"] = "FAIL"

            result["issue"] = "Website did not respond."

            result["possible_reason"] = "Server unavailable."

            result["recommendation"] = "Verify hosting."

            result["developer_action"] = "Check deployment."

            result["screenshot"] = save_screenshot(
                page,
                "website_open_failed.png"
            )

            return result

        if response.status >= 400:

            result["status"] = "FAIL"

            result["issue"] = f"HTTP Status : {response.status}"

            result["possible_reason"] = "Server Error"

            result["recommendation"] = "Verify backend deployment."

            result["developer_action"] = "Check server logs."

            result["screenshot"] = save_screenshot(
                page,
                "website_http_error.png"
            )

            return result

        title = page.title().strip()

        if title == "":

            result["status"] = "FAIL"

            result["issue"] = "Page title empty."

            result["possible_reason"] = "Frontend failed."

            result["recommendation"] = "Verify React build."

            result["developer_action"] = "Check frontend."

            result["screenshot"] = save_screenshot(
                page,
                "website_title_error.png"
            )

            return result

        # Performance Rating

        if load_time <= 2:

            result["performance"] = "Excellent"

        elif load_time <= 4:

            result["performance"] = "Good"

        elif load_time <= 6:

            result["performance"] = "Average"

        else:

            result["performance"] = "Slow"

            result["recommendation"] = (
                "Optimize CSS, JS, Images, Lazy Loading."
            )

            result["developer_action"] = (
                "Enable Cache, CDN & Compression."
            )

        result["screenshot"] = save_screenshot(
            page,
            "website_open_success.png"
        )

        print("Website Loaded Successfully")

        return result

    except Exception as e:

        result["status"] = "FAIL"

        result["issue"] = str(e)

        result["possible_reason"] = "Unexpected Exception"

        result["recommendation"] = "Verify website."

        result["developer_action"] = "Check logs."

        try:

            result["screenshot"] = save_screenshot(
                page,
                "website_exception.png"
            )

        except:
            pass

        return result

# =====================================
# Module 2
# Navigation Links
# =====================================

def navigation_links_test(page, url):

    result = create_result("Navigation Links")

    try:

        # Wait for React rendering
        page.wait_for_timeout(3000)

        safe_network_idle(page)

        # Find all links
        links = page.locator("a[href]")

        total_links = links.count()

        print(f"Found {total_links} navigation links")

        broken_links = []
        empty_links = []

        for i in range(total_links):

            try:

                link = links.nth(i)

                href = link.get_attribute("href")

                if href is None or href.strip() == "":

                    empty_links.append(
                        f"Link {i+1}"
                    )

                    continue

                if href.startswith("#"):
                    continue

                if href.startswith("javascript"):
                    continue

                if href.startswith("mailto:"):
                    continue

                if href.startswith("tel:"):
                    continue

                full_url = urljoin(url, href)

                response = page.request.get(
                    full_url,
                    timeout=10000
                )

                if response.status >= 400:

                    broken_links.append({
                        "url": full_url,
                        "status": response.status
                    })

            except Exception:

                broken_links.append({
                    "url": href,
                    "status": "No Response"
                })

        result["total_links"] = total_links
        result["details"] = len(broken_links)
        result["empty_links"] = len(empty_links)

        if broken_links or empty_links:

            result["status"] = "FAIL"

            issue = []

            if broken_links:

                issue.append(
                    f"{len(broken_links)} Broken Links"
                )

            if empty_links:

                issue.append(
                    f"{len(empty_links)} Empty Links"
                )

            result["issue"] = ", ".join(issue)

            result["possible_reason"] = (
                "Broken href or invalid routing."
            )

            result["recommendation"] = (
                "Verify all navigation links."
            )

            result["developer_action"] = (
                "Update routing or broken URLs."
            )

            result["details"] = broken_links

            result["screenshot"] = save_screenshot(
                page,
                "navigation_links_failed.png"
            )

        else:

            result["status"] = "PASS"

            result["screenshot"] = save_screenshot(
                page,
                "navigation_links_success.png"
            )

        print(
            f"Navigation Completed | Total:{total_links} "
            f"Broken:{len(broken_links)} Empty:{len(empty_links)}"
        )

        return result

    except Exception as e:

        result["status"] = "FAIL"

        result["issue"] = str(e)

        result["possible_reason"] = (
            "Navigation testing exception."
        )

        result["recommendation"] = (
            "Verify navigation."
        )

        result["developer_action"] = (
            "Review frontend routing."
        )

        try:

            result["screenshot"] = save_screenshot(
                page,
                "navigation_links_exception.png"
            )

        except:
            pass

        return result  
    
# =====================================
# Module 3
# Navbar Testing
# =====================================

def navbar_test(page):

    result = create_result("Navbar")

    try:

        # Wait for React rendering
        page.wait_for_timeout(3000)
        safe_network_idle(page)

        # Multiple navbar selectors
        navbar = page.locator(
            "nav, header, .navbar, .header, [role='navigation']"
        ).first

        if navbar.count() == 0:

            result["status"] = "FAIL"
            result["issue"] = "Navbar not found."
            result["possible_reason"] = "Navbar missing."
            result["recommendation"] = "Create navigation bar."
            result["developer_action"] = "Verify Header component."
            result["screenshot"] = save_screenshot(
                page,
                "navbar_missing.png"
            )

            return result

        print("Navbar Found")

        # ----------------------------
        # Logo Check
        # ----------------------------

        logo = navbar.locator("img")

        result["logo_found"] = logo.count() > 0

        # ----------------------------
        # Navbar Links
        # ----------------------------

        nav_links = navbar.locator("a[href]")

        total_links = nav_links.count()

        failed_links = []

        for i in range(total_links):

            try:

                link = nav_links.nth(i)

                href = link.get_attribute("href")

                try:
                    link_text = link.inner_text(
                        timeout=2000
                    ).strip()
                except Exception:
                    link_text = ""

                if not link_text:
                    link_text = (
                        link.get_attribute("aria-label")
                        or link.get_attribute("title")
                        or "(no text)"
                    )

                if not link.is_visible():

                    failed_links.append(
                        f"Hidden Link {i+1}: \"{link_text}\" "
                        f"-> {href or '(no href)'}"
                    )

                    continue

                if href is None:
                    continue

                if href.startswith("#"):
                    continue

                if href.startswith("javascript"):
                    continue

                response = page.request.get(
                    urljoin(page.url, href),
                    timeout=5000
                )

                if response.status >= 400:

                    failed_links.append(
                        f"\"{link_text}\" -> {href} "
                        f"({response.status})"
                    )

            except Exception as e:

                failed_links.append(
                    f"Link {i+1} ({str(e)})"
                )

        # ----------------------------
        # Sticky Navbar
        # ----------------------------

        sticky = page.evaluate("""
        () => {

            const nav =
                document.querySelector(
                    "nav,header,.navbar,.header,[role='navigation']"
                );

            if(!nav)
                return false;

            const style =
                window.getComputedStyle(nav);

            return style.position==="fixed" ||
                   style.position==="sticky";

        }
        """)

        result["sticky_navbar"] = sticky
        result["total_links"] = total_links
        result["failed_links"] = len(failed_links)
        result["failed_items"] = failed_links

        # ----------------------------
        # Mobile Menu
        # ----------------------------

        mobile_menu = page.locator("""
        button[aria-label*='menu'],
        button[aria-label*='Menu'],
        .menu-toggle,
        .hamburger
        """)

        result["mobile_menu"] = mobile_menu.count() > 0

        # ----------------------------
        # Final Result
        # ----------------------------

        if failed_links:

            result["status"] = "FAIL"

            result["issue"] = (
                f"{len(failed_links)} Navbar link(s) failed."
            )

            result["possible_reason"] = (
                "Broken routing."
            )

            result["recommendation"] = (
                "Verify Navbar links."
            )

            result["developer_action"] = (
                "Fix Header routing."
            )

            result["screenshot"] = save_screenshot(
                page,
                "navbar_failed.png"
            )

        else:

            result["status"] = "PASS"

            result["screenshot"] = save_screenshot(
                page,
                "navbar_success.png"
            )

        print(
            f"Navbar Checked | Links : {total_links} | Failed : {len(failed_links)}"
        )

        return result

    except Exception as e:

        result["status"] = "FAIL"

        result["issue"] = str(e)

        result["possible_reason"] = "Navbar testing exception."

        result["recommendation"] = "Verify navbar."

        result["developer_action"] = "Review Header component."

        try:

            result["screenshot"] = save_screenshot(
                page,
                "navbar_exception.png"
            )

        except:
            pass

        return result
    
# =====================================
# Module 4
# Footer Testing
# =====================================

def footer_test(page, url):

    result = create_result("Footer")

    try:

        print("\n========== FOOTER TEST START ==========")

        page.wait_for_timeout(3000)
        safe_network_idle(page)

        print("Searching Footer...")

        footer = page.locator(
            "footer, .footer, #footer"
        ).first

        if footer.count() == 0:

            print("❌ Footer NOT Found")

            result["status"] = "FAIL"
            result["issue"] = "Footer not found."
            result["possible_reason"] = "Footer missing."
            result["recommendation"] = "Add footer section."
            result["developer_action"] = "Verify Footer component."
            result["screenshot"] = save_screenshot(
                page,
                "footer_missing.png"
            )

            return result

        print("✅ Footer Found")

        if not footer.is_visible():

            print("❌ Footer Hidden")

            result["status"] = "FAIL"
            result["issue"] = "Footer not visible."
            result["possible_reason"] = "CSS issue."
            result["recommendation"] = "Display footer correctly."
            result["developer_action"] = "Check Footer CSS."
            result["screenshot"] = save_screenshot(
                page,
                "footer_hidden.png"
            )

            return result

        # -----------------------------
        # Footer Links
        # -----------------------------

        links = footer.locator("a[href]")

        total_links = links.count()

        print(f"Footer Links Found : {total_links}")

        broken_links = []

        for i in range(total_links):

            try:

                href = links.nth(i).get_attribute("href")

                print(f"[{i+1}] Checking -> {href}")

                if href is None:
                    continue

                if href.startswith("#"):
                    continue

                if href.startswith("javascript"):
                    continue

                if href.startswith("mailto:"):
                    continue

                if href.startswith("tel:"):
                    continue

                full_url = urljoin(url, href)

                response = page.request.get(
                    full_url,
                    timeout=5000
                )

                print(
                    f"Status : {response.status}"
                )

                if response.status >= 400:

                    broken_links.append(
                        {
                            "url": full_url,
                            "status": response.status
                        }
                    )

            except Exception as e:

                print(
                    f"Broken : {href}"
                )

                print(e)

                broken_links.append(
                    {
                        "url": href,
                        "status": "No Response"
                    }
                )

        # -----------------------------
        # Social Links
        # -----------------------------

        social_links = footer.locator(
            """
            a[href*='facebook'],
            a[href*='instagram'],
            a[href*='linkedin'],
            a[href*='twitter'],
            a[href*='youtube']
            """
        ).count()

        print(
            f"Social Links : {social_links}"
        )

        # -----------------------------
        # Contact Details
        # -----------------------------

        contact_found = footer.locator(
            "text=/@|\\+91|gmail|phone|contact/i"
        ).count()

        print(
            f"Contact Found : {contact_found}"
        )

        # -----------------------------
        # Copyright
        # -----------------------------

        copyright_found = footer.locator(
            "text=/copyright|©/i"
        ).count()

        print(
            f"Copyright : {copyright_found}"
        )

        result["footer_links"] = total_links
        result["broken_links"] = len(broken_links)
        result["social_links"] = social_links
        result["contact_found"] = contact_found > 0
        result["copyright_found"] = copyright_found > 0

        if broken_links:

            print(
                f"❌ Broken Links : {len(broken_links)}"
            )

            result["status"] = "FAIL"
            result["issue"] = f"{len(broken_links)} Broken Footer Links."
            result["possible_reason"] = "Invalid URL."
            result["recommendation"] = "Update Footer Links."
            result["developer_action"] = "Verify Footer Routing."
            result["details"] = broken_links
            result["screenshot"] = save_screenshot(
                page,
                "footer_failed.png"
            )

        else:

            print("✅ Footer Passed")

            result["status"] = "PASS"

            result["screenshot"] = save_screenshot(
                page,
                "footer_success.png"
            )

        print("========== FOOTER TEST END ==========\n")

        return result

    except Exception as e:

        print("Footer Exception")

        print(e)

        result["status"] = "FAIL"
        result["issue"] = str(e)
        result["possible_reason"] = "Footer testing exception."
        result["recommendation"] = "Verify Footer."
        result["developer_action"] = "Review Footer."

        try:

            result["screenshot"] = save_screenshot(
                page,
                "footer_exception.png"
            )

        except:
            pass

        return result
    
# =====================================
# Module 5
# Buttons Testing
# =====================================

def buttons_test(page):

    result = create_result("Buttons")

    try:

        print("\n========== BUTTON TEST START ==========")

        # ------------------------------------------------
        # PAGE READY
        # ------------------------------------------------

        print("[5.1] Preparing page...")

        page.wait_for_load_state(
            "domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(2000)

        print(f"Current URL : {page.url}")

        # ------------------------------------------------
        # FIND BUTTONS
        # ------------------------------------------------

        print("\n[5.2] Finding visible buttons...")

        buttons = page.locator(
            "button:visible, "
            "input[type='submit']:visible, "
            "input[type='button']:visible, "
            "a[role='button']:visible"
        )

        total_detected = buttons.count()

        print(
            f"Detected Visible Buttons : "
            f"{total_detected}"
        )

        if total_detected == 0:

            print("❌ No buttons found")

            result["status"] = "FAIL"
            result["issue"] = "No visible buttons found."
            result["possible_reason"] = (
                "Website may not contain interactive buttons."
            )
            result["recommendation"] = (
                "Verify the frontend button elements."
            )
            result["developer_action"] = (
                "Check button components and selectors."
            )

            result["screenshot"] = save_screenshot(
                page,
                "buttons_missing.png"
            )

            return result

        # ------------------------------------------------
        # CREATE UNIQUE BUTTON LIST
        # ------------------------------------------------

        print("\n[5.3] Preparing unique button list...")

        button_data = []
        seen = set()

        for i in range(total_detected):

            try:

                button = buttons.nth(i)

                # Get text safely
                try:
                    text = button.inner_text(
                        timeout=2000
                    ).strip()
                except:
                    text = ""

                # For input buttons
                if text == "":

                    try:
                        text = button.get_attribute(
                            "value"
                        ) or ""
                    except:
                        pass

                # For aria-label
                if text == "":

                    try:
                        text = button.get_attribute(
                            "aria-label"
                        ) or ""
                    except:
                        pass

                text = text.strip()

                if text == "":
                    text = f"Button {i + 1}"

                # Unique key
                key = (
                    text,
                    button.get_attribute("type"),
                    button.get_attribute("href")
                )

                if key not in seen:

                    seen.add(key)

                    button_data.append(
                        {
                            "index": i,
                            "text": text
                        }
                    )

            except Exception as e:

                print(
                    f"⚠️ Could not inspect button "
                    f"{i + 1}: {e}"
                )

        print(
            f"Unique Visible Buttons : "
            f"{len(button_data)}"
        )

        # ------------------------------------------------
        # JAVASCRIPT ERROR MONITORING
        # ------------------------------------------------

        js_errors = []

        def handle_page_error(error):

            try:
                js_errors.append(
                    str(error)
                )
            except:
                pass

        page.on(
            "pageerror",
            handle_page_error
        )

        # ------------------------------------------------
        # TEST BUTTONS
        # ------------------------------------------------

        passed_buttons = []
        failed_buttons = []

        for position, data in enumerate(
            button_data,
            start=1
        ):

            text = data["text"]
            before_url = page.url  # FIX: default so cleanup code below never hits an unbound variable

            print("\n--------------------------------")
            print(
                f"Checking Button : "
                f"{position}"
            )
            print(
                f"Text : {text}"
            )

            try:

                # Re-fetch buttons every time
                # because page DOM may change
                current_buttons = page.locator(
                    "button:visible, "
                    "input[type='submit']:visible, "
                    "input[type='button']:visible, "
                    "a[role='button']:visible"
                )

                target = None

                # ------------------------------------------------
                # FIND SAME BUTTON BY TEXT
                # ------------------------------------------------

                for j in range(
                    current_buttons.count()
                ):

                    candidate = current_buttons.nth(j)

                    try:

                        candidate_text = ""

                        try:
                            candidate_text = (
                                candidate.inner_text(
                                    timeout=1000
                                ).strip()
                        )
                        except:
                            pass

                        if candidate_text == "":

                            try:
                                candidate_text = (
                                    candidate.get_attribute(
                                        "value"
                                    ) or ""
                                ).strip()
                            except:
                                pass

                        if candidate_text == "":

                            try:
                                candidate_text = (
                                    candidate.get_attribute(
                                        "aria-label"
                                    ) or ""
                                ).strip()
                            except:
                                pass

                        if candidate_text == text:

                            target = candidate
                            break

                    except:
                        continue

                # ------------------------------------------------
                # IF TEXT MATCH FAILED, USE ORIGINAL INDEX
                # ------------------------------------------------

                if target is None:

                    original_index = data["index"]

                    if (
                        original_index
                        <
                        current_buttons.count()
                    ):

                        target = (
                            current_buttons.nth(
                                original_index
                            )
                        )

                if target is None:

                    print(
                        "❌ Button could not be located"
                    )

                    failed_buttons.append(
                        f"{text} (Button not found)"
                    )

                    continue

                # ------------------------------------------------
                # VISIBILITY
                # ------------------------------------------------

                visible = target.is_visible()

                print(
                    f"Visible : {visible}"
                )

                if not visible:

                    print(
                        "❌ Button not visible"
                    )

                    failed_buttons.append(
                        f"{text} (Hidden)"
                    )

                    continue

                # ------------------------------------------------
                # ENABLED
                # ------------------------------------------------

                try:

                    enabled = target.is_enabled()

                except:

                    enabled = True

                print(
                    f"Enabled : {enabled}"
                )

                if not enabled:

                    print(
                        "❌ Button disabled"
                    )

                    failed_buttons.append(
                        f"{text} (Disabled)"
                    )

                    continue

                # ------------------------------------------------
                # RECORD BEFORE STATE
                # ------------------------------------------------

                before_url = page.url

                before_count = page.locator(
                    "body"
                ).inner_text(
                    timeout=3000
                )

                before_error_count = len(
                    js_errors
                )

                print(
                    f"Before URL : "
                    f"{before_url}"
                )

                # ------------------------------------------------
                # CLICK
                # ------------------------------------------------

                print(
                    "Clicking..."
                )

                target.click(
                    timeout=5000,
                    force=True,
                    no_wait_after=True
                )

                page.wait_for_timeout(
                    1500
                )

                # ------------------------------------------------
                # AFTER STATE
                # ------------------------------------------------

                after_url = page.url

                try:

                    after_count = page.locator(
                        "body"
                    ).inner_text(
                        timeout=3000
                    )

                except:

                    after_count = before_count

                after_error_count = len(
                    js_errors
                )

                print(
                    f"After URL  : "
                    f"{after_url}"
                )

                # ------------------------------------------------
                # ACTION DETECTION
                # ------------------------------------------------

                url_changed = (
                    after_url
                    !=
                    before_url
                )

                content_changed = (
                    after_count
                    !=
                    before_count
                )

                js_error_created = (
                    after_error_count
                    >
                    before_error_count
                )

                # Check common UI changes
                dialogs = page.locator(
                    "[role='dialog']:visible, "
                    "[aria-modal='true']:visible"
                )

                menus = page.locator(
                    "[role='menu']:visible, "
                    "[role='listbox']:visible"
                )

                search_inputs = page.locator(
                    "input[type='search']:visible, "
                    "input[placeholder*='Search' i]:visible"
                )

                try:
                    dialog_visible = (
                        dialogs.count() > 0
                    )
                except:
                    dialog_visible = False

                try:
                    menu_visible = (
                        menus.count() > 0
                    )
                except:
                    menu_visible = False

                try:
                    search_visible = (
                        search_inputs.count() > 0
                    )
                except:
                    search_visible = False

                # ------------------------------------------------
                # RESULT
                # ------------------------------------------------

                if js_error_created:

                    print(
                        "❌ JavaScript error "
                        "occurred after click"
                    )

                    failed_buttons.append(
                        f"{text} "
                        f"(JavaScript error)"
                    )

                elif (
                    url_changed
                    or
                    content_changed
                    or
                    dialog_visible
                    or
                    menu_visible
                    or
                    search_visible
                ):

                    print(
                        "✅ Button action detected"
                    )

                    if url_changed:
                        print(
                            "   ↳ URL changed"
                        )

                    if content_changed:
                        print(
                            "   ↳ Page content changed"
                        )

                    if dialog_visible:
                        print(
                            "   ↳ Dialog opened"
                        )

                    if menu_visible:
                        print(
                            "   ↳ Menu/Listbox opened"
                        )

                    if search_visible:
                        print(
                            "   ↳ Search interface opened"
                        )

                    passed_buttons.append(
                        text
                    )

                else:

                    # Important:
                    # Same URL alone is NOT a failure.
                    # The click itself completed successfully,
                    # but no observable UI action was detected.

                    print(
                        "⚠️ Click completed"
                    )

                    print(
                        "   ↳ URL unchanged"
                    )

                    print(
                        "   ↳ No visible UI/content change detected"
                    )

                    failed_buttons.append(
                        f"{text} "
                        f"(No observable action)"
                    )

            except Exception as e:

                print(
                    "❌ Click Failed"
                )

                print(
                    f"Error : {e}"
                )

                failed_buttons.append(
                    f"{text} ({str(e)})"
                )

            # ------------------------------------------------
            # RETURN TO ORIGINAL PAGE
            # ------------------------------------------------

            try:

                if page.url != before_url:

                    print(
                        "Returning to original page..."
                    )

                    page.goto(
                        before_url,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )

                    page.wait_for_timeout(
                        1500
                    )

            except Exception as e:

                print(
                    f"⚠️ Could not return to page: "
                    f"{e}"
                )

        # ------------------------------------------------
        # FINAL COUNTS
        # ------------------------------------------------

        print("\n================================")

        print(
            f"Total Buttons  : "
            f"{len(button_data)}"
        )

        print(
            f"Passed Buttons : "
            f"{len(passed_buttons)}"
        )

        print(
            f"Failed Buttons : "
            f"{len(failed_buttons)}"
        )

        print("================================")

        # ------------------------------------------------
        # RESULT
        # ------------------------------------------------

        result["total_buttons"] = (
            len(button_data)
        )

        result["passed_buttons"] = (
            len(passed_buttons)
        )

        result["failed_buttons"] = (
            len(failed_buttons)
        )

        result["javascript_errors"] = (
            js_errors
        )

        result["details"] = (
            failed_buttons
        )

        # ------------------------------------------------
        # STATUS
        # ------------------------------------------------

        if failed_buttons:

            result["status"] = "FAIL"

            result["issue"] = (
                f"{len(failed_buttons)} "
                f"Button(s) Failed."
            )

            result["possible_reason"] = (
                "Button click produced no "
                "observable action or an error occurred."
            )

            result["recommendation"] = (
                "Verify onclick handlers, routing, "
                "dropdowns, modals and interactive UI behaviour."
            )

            result["developer_action"] = (
                "Review frontend button event handlers."
            )

            result["screenshot"] = (
                save_screenshot(
                    page,
                    "buttons_failed.png"
                )
            )

        else:

            result["status"] = "PASS"

            result["issue"] = ""

            result["possible_reason"] = ""

            result["recommendation"] = (
                "All tested buttons performed "
                "a valid observable action."
            )

            result["developer_action"] = ""

            result["screenshot"] = (
                save_screenshot(
                    page,
                    "buttons_success.png"
                )
            )

        print(
            "========== BUTTON TEST END ==========\n"
        )

        return result

    # ------------------------------------------------
    # MODULE EXCEPTION
    # ------------------------------------------------

    except Exception as e:

        print(
            "\n❌ BUTTON MODULE EXCEPTION"
        )

        print(
            f"Error : {e}"
        )

        result["status"] = "FAIL"

        result["issue"] = str(e)

        result["possible_reason"] = (
            "Unexpected button testing exception."
        )

        result["recommendation"] = (
            "Verify button selectors and Playwright execution."
        )

        result["developer_action"] = (
            "Review button testing logs."
        )

        try:

            result["screenshot"] = (
                save_screenshot(
                    page,
                    "buttons_exception.png"
                )
            )

        except:

            result["screenshot"] = ""

        return result    
    
    
    
# =====================================
# Module 6
# Form Validation (Part 6.1)
# =====================================

def form_validation_test(page):

    result = create_result("Form Validation")

    try:

        print("\n========== FORM VALIDATION START ==========")

        page.wait_for_timeout(3000)
        safe_network_idle(page)

        # -----------------------------
        # Detect Forms
        # -----------------------------

        forms = page.locator("form")

        total_forms = forms.count()

        print(f"Total Forms Found : {total_forms}")

        # Fallback (React apps)
        if total_forms == 0:

            print("No <form> tag found.")
            print("Searching Input Groups...")

            forms = page.locator(
                "input, textarea, select"
            )

            if forms.count() > 0:

                total_forms = 1

                print("Input controls detected.")

        if total_forms == 0:

            result["status"] = "FAIL"

            result["issue"] = "No Forms Found"

            result["possible_reason"] = "Website has no forms."

            result["recommendation"] = "Verify Login / Contact Form."

            result["developer_action"] = "Check frontend forms."

            result["screenshot"] = save_screenshot(
                page,
                "form_missing.png"
            )

            return result

        # -----------------------------
        # Collect Inputs
        # -----------------------------

        inputs = page.locator(
            "input, textarea, select"
        )

        total_inputs = inputs.count()

        print(f"Total Inputs : {total_inputs}")

        input_details = []

        for i in range(total_inputs):

            try:

                control = inputs.nth(i)

                input_type = control.get_attribute("type")

                if input_type is None:
                    input_type = "text"

                placeholder = control.get_attribute("placeholder") or ""

                name = control.get_attribute("name") or ""

                required = control.get_attribute("required")

                visible = control.is_visible()

                enabled = control.is_enabled()

                print(
                    f"[{i+1}] "
                    f"Type={input_type} | "
                    f"Name={name} | "
                    f"Placeholder={placeholder}"
                )

                input_details.append({

                    "type": input_type,

                    "name": name,

                    "placeholder": placeholder,

                    "required": required is not None,

                    "visible": visible,

                    "enabled": enabled

                })

            except Exception as e:

                print(e)

        result["total_forms"] = total_forms
        result["total_inputs"] = total_inputs
        result["input_details"] = input_details

        result["status"] = "PASS"

        result["screenshot"] = save_screenshot(
            page,
            "form_detect_success.png"
        )

        print("========== FORM DETECTION COMPLETED ==========\n")

        # -----------------------------
        # Required Field Validation
        # -----------------------------

        print("\n========== REQUIRED FIELD VALIDATION ==========")

        required_failed = []

        for i in range(total_inputs):

            try:

                control = inputs.nth(i)

                input_type = control.get_attribute("type") or "text"

                name = control.get_attribute("name") or ""

                placeholder = control.get_attribute("placeholder") or ""

                required = control.get_attribute("required")

                visible = control.is_visible()

                enabled = control.is_enabled()

                field_name = (
                    name
                    if name != ""
                    else placeholder
                    if placeholder != ""
                    else f"Field {i+1}"
                )

                print("--------------------------------")
                print(f"Checking : {field_name}")
                print(f"Type      : {input_type}")
                print(f"Visible   : {visible}")
                print(f"Enabled   : {enabled}")
                print(f"Required  : {required is not None}")

                if not visible:

                    print("❌ Hidden Field")

                    required_failed.append(
                        f"{field_name} (Hidden)"
                    )

                    continue

                if not enabled:

                    print("❌ Disabled Field")

                    required_failed.append(
                        f"{field_name} (Disabled)"
                    )

                    continue

                if required is not None:

                    print("Testing Empty Validation...")

                    control.fill("")

                    control.press("Tab")

                    page.wait_for_timeout(300)

                    valid = page.evaluate("""
                    (el)=>{
                        return el.checkValidity();
                    }
                    """, control.element_handle())

                    print(f"HTML Validation : {valid}")

                    if valid:

                        print("❌ Required validation NOT working")

                        required_failed.append(
                            f"{field_name} (Required Validation Failed)"
                        )

                    else:

                        print("✅ Required validation Working")

            except Exception as e:

                print(e)

                required_failed.append(
                    f"Field {i+1} ({str(e)})"
                )

        print("\n======================================")
        print(f"Required Validation Failed : {len(required_failed)}")
        print("======================================")

        result["required_validation_failed"] = len(required_failed)
        result["required_validation_details"] = required_failed

        # -----------------------------
        # Email / Phone / Password Validation
        # -----------------------------

        print("\n========== EMAIL / PHONE / PASSWORD VALIDATION ==========")

        validation_failed = []

        for i in range(total_inputs):

            try:

                control = inputs.nth(i)

                input_type = (control.get_attribute("type") or "").lower()

                name = (control.get_attribute("name") or "").lower()

                placeholder = (control.get_attribute("placeholder") or "").lower()

                field = f"{name} {placeholder}"

                # -----------------------------
                # EMAIL
                # -----------------------------
                if input_type == "email" or "email" in field:

                    print("\n--------------------------------")
                    print("Checking EMAIL Validation")

                    control.fill("abc")

                    control.press("Tab")

                    page.wait_for_timeout(500)

                    valid = page.evaluate("""
                    (el)=>{
                        return el.checkValidity();
                    }
                    """, control.element_handle())

                    print(f"Entered : abc")
                    print(f"Validation : {valid}")

                    if valid:

                        print("❌ Invalid Email Accepted")

                        validation_failed.append(
                            "Email Validation Failed"
                        )

                    else:

                        print("✅ Email Validation Working")

                # -----------------------------
                # PHONE
                # -----------------------------
                elif input_type == "tel" or "phone" in field or "mobile" in field:

                    print("\n--------------------------------")
                    print("Checking PHONE Validation")

                    control.fill("123")

                    control.press("Tab")

                    page.wait_for_timeout(500)

                    value = control.input_value()

                    print(f"Entered : {value}")

                    if len(value) < 10:

                        print("✅ Phone Validation Working")

                    else:

                        print("❌ Phone Validation Failed")

                        validation_failed.append(
                            "Phone Validation Failed"
                        )

                # -----------------------------
                # PASSWORD
                # -----------------------------
                elif input_type == "password":

                    print("\n--------------------------------")
                    print("Checking PASSWORD Validation")

                    control.fill("123")

                    control.press("Tab")

                    page.wait_for_timeout(500)

                    value = control.input_value()

                    print(f"Entered : {value}")

                    if len(value) < 6:

                        print("✅ Password Rule Triggered")

                    else:

                        print("❌ Weak Password Accepted")

                        validation_failed.append(
                            "Password Validation Failed"
                        )

            except Exception as e:

                print(e)

                validation_failed.append(str(e))

        print("\n======================================")
        print(f"Validation Failed : {len(validation_failed)}")
        print("======================================")

        result["validation_failed"] = len(validation_failed)
        result["validation_details"] = validation_failed

        # -----------------------------
        # Form Submit Validation
        # -----------------------------

        print("\n========== FORM SUBMIT VALIDATION ==========")

        submit_failed = []

        try:

            submit_buttons = page.locator(
                "button[type='submit'], input[type='submit']"
            )

            total_submit = submit_buttons.count()

            print(f"Submit Buttons Found : {total_submit}")

            if total_submit == 0:

                print("⚠ No Submit Button Found")

                result["submit_button"] = False

            else:

                submit = submit_buttons.first

                print("Clicking Submit Button...")

                submit.click(force=True)

                page.wait_for_timeout(3000)

                # -----------------------------
                # Success Message
                # -----------------------------

                success = page.locator(
                    "text=/success|submitted|thank you|completed/i"
                )

                success_found = success.count() > 0

                print(f"Success Message : {success_found}")

                # -----------------------------
                # Error Message
                # -----------------------------

                error = page.locator(
                    "text=/required|invalid|error|failed/i"
                )

                error_found = error.count() > 0

                print(f"Error Message : {error_found}")

                result["submit_button"] = True
                result["success_message"] = success_found
                result["error_message"] = error_found

                if success_found:

                    print("✅ Form Submitted Successfully")

                elif error_found:

                    print("⚠ Validation Error Displayed")

                else:

                    print("❌ No Response After Submit")

                    submit_failed.append(
                        "No Success/Error Message"
                    )

        except Exception as e:

            print("❌ Submit Exception")
            print(e)

            submit_failed.append(str(e))

        print("\n======================================")
        print(f"Submit Failed : {len(submit_failed)}")
        print("======================================")

        result["submit_failed"] = len(submit_failed)
        result["submit_details"] = submit_failed

        return result

    except Exception as e:

        print(e)

        result["status"] = "FAIL"

        result["issue"] = str(e)

        result["possible_reason"] = "Form Detection Exception"

        result["recommendation"] = "Verify Forms."

        result["developer_action"] = "Review frontend."

        try:

            result["screenshot"] = save_screenshot(
                page,
                "form_exception.png"
            )

        except:
            pass

        return result

# =====================================
# Module 6.5
# Broken Images
# =====================================

def broken_images_test(page):

    result = create_result("Broken Images")

    try:

        print("\n========== BROKEN IMAGES TEST START ==========")

        page.wait_for_timeout(3000)
        safe_network_idle(page)

        images = page.locator("img")

        total_images = images.count()

        print(f"Total Images Found : {total_images}")

        broken_images = []

        for i in range(total_images):

            try:

                img = images.nth(i)

                src = img.get_attribute("src")

                if not src:
                    print(f"[{i+1}] Image has no src")
                    broken_images.append("Missing src")
                    continue

                print(f"[{i+1}] Checking : {src}")

                is_loaded = page.evaluate(
                    """
                    (element) => {
                        return element.complete &&
                               element.naturalWidth > 0;
                    }
                    """,
                    img
                )

                if not is_loaded:

                    print("❌ Broken Image")

                    broken_images.append(src)

                else:

                    print("✅ Image Loaded")

            except Exception as e:

                print(f"❌ Exception : {e}")

                broken_images.append(str(e))

        result["total_images"] = total_images
        result["broken_images"] = len(broken_images)

        if broken_images:

            print(f"\nBroken Images : {len(broken_images)}")

            result["status"] = "FAIL"
            result["issue"] = f"{len(broken_images)} Broken Image(s)"
            result["possible_reason"] = "Invalid image path."
            result["recommendation"] = "Replace broken image URLs."
            result["developer_action"] = "Verify image assets."
            result["details"] = broken_images

            result["screenshot"] = save_screenshot(
                page,
                "broken_images_failed.png"
            )

        else:

            print("\n✅ All Images Loaded Successfully")

            result["status"] = "PASS"

            result["screenshot"] = save_screenshot(
                page,
                "broken_images_success.png"
            )

        print("========== BROKEN IMAGES TEST END ==========\n")

        return result

    except Exception as e:

        print("\n❌ BROKEN IMAGE MODULE EXCEPTION")
        print(e)

        result["status"] = "FAIL"
        result["issue"] = str(e)
        result["possible_reason"] = "Broken image test exception."
        result["recommendation"] = "Verify image loading."
        result["developer_action"] = "Review frontend assets."

        try:
            result["screenshot"] = save_screenshot(
                page,
                "broken_images_exception.png"
            )
        except:
            pass

        return result            
 
# =====================================
# Module 7
# Image Testing
# =====================================

def image_test(page, url):

    result = create_result("Images")

    try:
        
        # =====================================
        # Part 7.1
        # =====================================
        print("\n======================================")
        print("IMAGE TEST START")
        print("======================================")

        page.wait_for_timeout(3000)
        safe_network_idle(page)

        # Collect all images

        images = page.locator("img")

        total_images = images.count()

        print(f"Total Images Found : {total_images}")

        result["total_images"] = total_images

        if total_images == 0:

            print("❌ No Images Found")

            result["status"] = "FAIL"

            result["issue"] = "No images found."

            result["possible_reason"] = "Website contains no img tags."

            result["recommendation"] = "Add website images."

            result["developer_action"] = "Verify frontend."

            result["screenshot"] = save_screenshot(
                page,
                "images_missing.png"
            )

            return result

        broken_images = []

        missing_alt = []

        hidden_images = []

        lazy_images = []

        image_details = []

        print("--------------------------------------")
        print("Starting Image Scan...")
        print("--------------------------------------")

        # =====================================
        # Part 7.2 (Loop Through Images)
        # =====================================

        for i in range(total_images):

            print("\n--------------------------------------")
            print(f"Checking Image : {i+1}/{total_images}")

            try:

                image = images.nth(i)

                src = image.get_attribute("src")
                alt = image.get_attribute("alt")
                loading = image.get_attribute("loading")

                print(f"SRC      : {src}")
                print(f"ALT      : {alt}")
                print(f"Loading  : {loading}")

                visible = image.is_visible()

                print(f"Visible  : {visible}")

                # Save details

                image_details.append({

                    "src": src,

                    "alt": alt,

                    "visible": visible,

                    "loading": loading

                })

                # -------------------------
                # Hidden Image
                # -------------------------

                if not visible:

                    print("❌ Hidden Image")

                    hidden_images.append(src)

                # -------------------------
                # Missing ALT
                # -------------------------

                if alt is None or alt.strip() == "":

                    print("❌ Missing ALT")

                    missing_alt.append(src)

                else:

                    print("✅ ALT Available")

                # -------------------------
                # Lazy Loading
                # -------------------------

                if loading == "lazy":

                    print("✅ Lazy Loading Enabled")

                    lazy_images.append(src)

                # -------------------------
                # Broken Image Check
                # -------------------------

                if src:

                    try:

                        full_url = urljoin(url, src)

                        print(f"Checking URL : {full_url}")

                        response = page.request.get(

                            full_url,

                            timeout=10000

                        )

                        print(f"HTTP Status : {response.status}")

                        if response.status >= 400:

                            print("❌ Broken Image")

                            broken_images.append({

                                "src": full_url,

                                "status": response.status

                            })

                        else:

                            print("✅ Image Working")

                    except Exception as e:

                        print("❌ Image Request Failed")

                        print(e)

                        broken_images.append({

                            "src": src,

                            "status": "No Response"

                        })

            except Exception as e:

                print("❌ Image Exception")

                print(e)

        # =====================================
        # Part 7.3
        # Image Dimension & Duplicate Check
        # =====================================

        print("\n======================================")
        print("IMAGE DIMENSION CHECK")
        print("======================================")

        duplicate_images = []
        small_images = []

        checked_src = []

        for img in image_details:

            src = img["src"]

            if not src:
                continue

            # -------------------------
            # Duplicate Image
            # -------------------------

            if src in checked_src:

                print(f"❌ Duplicate Image : {src}")

                duplicate_images.append(src)

            else:

                checked_src.append(src)

                print(f"✅ Unique Image : {src}")

            # -------------------------
            # Width / Height
            # -------------------------

            try:

                locator = page.locator(f'img[src="{src}"]').first

                width = locator.evaluate(
                    "(el)=>el.naturalWidth"
                )

                height = locator.evaluate(
                    "(el)=>el.naturalHeight"
                )

                print(f"Width  : {width}")
                print(f"Height : {height}")

                if width < 100 or height < 100:

                    print("⚠ Small Image")

                    small_images.append({

                        "src": src,

                        "width": width,

                        "height": height

                    })

                else:

                    print("✅ Image Resolution OK")

            except Exception as e:

                print("Image Dimension Error")

                print(e)

        result["duplicate_images"] = len(duplicate_images)
        result["small_images"] = len(small_images)
        result["duplicate_details"] = duplicate_images
        result["small_image_details"] = small_images

        print("\n======================================")
        print(f"Duplicate Images : {len(duplicate_images)}")
        print(f"Small Images     : {len(small_images)}")
        print("======================================")
        
        # =====================================
        # Part 7.4
        # Final Result
        # =====================================

        print("\n======================================")
        print("IMAGE TEST SUMMARY")
        print("======================================")

        print(f"Total Images      : {total_images}")
        print(f"Broken Images     : {len(broken_images)}")
        print(f"Missing ALT       : {len(missing_alt)}")
        print(f"Hidden Images     : {len(hidden_images)}")
        print(f"Lazy Loaded       : {len(lazy_images)}")
        print(f"Duplicate Images  : {len(duplicate_images)}")
        print(f"Small Images      : {len(small_images)}")

        result["broken_images"] = len(broken_images)
        result["missing_alt"] = len(missing_alt)
        result["hidden_images"] = len(hidden_images)
        result["lazy_loaded"] = len(lazy_images)

        result["broken_image_details"] = broken_images
        result["missing_alt_details"] = missing_alt
        result["hidden_image_details"] = hidden_images

        # -------------------------
        # PASS / FAIL
        # -------------------------

        if (
            broken_images or
            missing_alt or
            hidden_images
        ):

            print("\n❌ IMAGE TEST FAILED")

            result["status"] = "FAIL"

            issues = []

            if broken_images:
                issues.append(f"{len(broken_images)} Broken Images")

            if missing_alt:
                issues.append(f"{len(missing_alt)} Missing ALT")

            if hidden_images:
                issues.append(f"{len(hidden_images)} Hidden Images")

            result["issue"] = ", ".join(issues)

            result["possible_reason"] = (
                "Image loading or accessibility issue."
            )

            result["recommendation"] = (
                "Fix broken images, add ALT text and verify visibility."
            )

            result["developer_action"] = (
                "Review frontend image rendering."
            )

            result["screenshot"] = save_screenshot(
                page,
                "image_test_failed.png"
            )

        else:

            print("\n✅ IMAGE TEST PASSED")

            result["status"] = "PASS"

            result["screenshot"] = save_screenshot(
                page,
                "image_test_success.png"
            )

        print("======================================")
        print("IMAGE TEST COMPLETED")
        print("======================================")

        return result

    except Exception as e:

        print("\n❌ IMAGE MODULE EXCEPTION")
        print(e)

        result["status"] = "FAIL"

        result["issue"] = str(e)

        result["possible_reason"] = (
            "Unexpected exception during image testing."
        )

        result["recommendation"] = (
            "Verify image loading."
        )

        result["developer_action"] = (
            "Review image module."
        )

        try:

            result["screenshot"] = save_screenshot(
                page,
                "image_test_exception.png"
            )

        except:
            pass

        return result
    
# =====================================
# Module 8 : Content Validation
# Part 1 : Detect Text Elements
# =====================================
def content_validation_test(page):

    result = {

        "module": "Content Validation",
        "status": "PASS",
        "page_load_time": 0,
        "performance": "",
        "issue": "",
        "possible_reason": "",
        "recommendation": "",
        "developer_action": "",
        "screenshot": "",

        "total_text_blocks": 0,
        "text_details": [],

        "empty_text": 0,
        "empty_text_details": [],

        "lorem_ipsum": 0,
        "lorem_details": [],

        "duplicate_heading": 0,
        "duplicate_heading_details": [],

        "missing_h1": False,
        "missing_meta_description": False,

        "word_count": 0

    }

    print("\n======================================")
    print("CONTENT VALIDATION START")
    print("======================================")

    try:

        page.goto(page.url)

        safe_network_idle(page)

        selectors = [
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
            "span",
            "label",
            "button",
            "a",
            "li"
        ]

        elements = []
        for selector in selectors:

            try:

                locator = page.locator(selector)

                count = locator.count()

                print(f"{selector} : {count}")

                for i in range(count):

                    text = locator.nth(i).inner_text().strip()

                    elements.append(text)

            except Exception as e:

                print(f"{selector} Error")
                print(e)

        result["total_text_blocks"] = len(elements)

        print(f"Total Text Elements : {len(elements)}")

        console_errors = []
        page.on(
            "console",
            lambda msg: (
                console_errors.append(msg.text)
                if msg.type == "error"
                else None
            )
        )

        # ======================================
        # 8.2 CSS & JavaScript Resource Test
        # ======================================

        print("\n======================================")
        print("CSS & JS RESOURCE TEST")
        print("======================================")

        css_files = page.locator("link[rel='stylesheet']").evaluate_all(
            "(els) => els.map(e => e.href)"
        )

        js_files = page.locator("script[src]").evaluate_all(
            "(els) => els.map(e => e.src)"
        )

        broken_css = 0
        broken_js = 0

        print(f"CSS Files : {len(css_files)}")
        print(f"JS Files  : {len(js_files)}")

        # ---------- CSS ----------
        for css in css_files:

            try:

                response = page.request.get(css)

                print("--------------------------------")
                print(f"CSS : {css}")
                print(f"Status : {response.status}")

                if response.status >= 400:

                    print("❌ Broken CSS")
                    broken_css += 1

                else:

                    print("✅ CSS Loaded")

            except Exception:

                print("❌ CSS Request Failed")
                broken_css += 1


        # ---------- JS ----------
        for js in js_files:

            try:

                response = page.request.get(js)

                print("--------------------------------")
                print(f"JS : {js}")
                print(f"Status : {response.status}")

                if response.status >= 400:

                    print("❌ Broken JS")
                    broken_js += 1

                else:

                    print("✅ JS Loaded")

            except Exception:

                print("❌ JS Request Failed")
                broken_js += 1


        result["css_files"] = len(css_files)
        result["js_files"] = len(js_files)
        result["broken_css"] = broken_css
        result["broken_js"] = broken_js

        print("\n======================================")
        print(f"Broken CSS : {broken_css}")
        print(f"Broken JS  : {broken_js}")
        print("======================================")

        # ======================================
        # Broken CSS / JS Summary
        # ======================================

        print("\n======================================")
        print("BROKEN CSS / JS SUMMARY")
        print("======================================")

        print(f"Total CSS Files        : {len(css_files)}")
        print(f"Broken CSS Files       : {broken_css}")

        print("\n--------------------------------------")

        print(f"Total JS Files         : {len(js_files)}")
        print(f"Broken JS Files        : {broken_js}")

        print("\n--------------------------------------")

        print(f"Console Errors         : {len(console_errors)}")

        if console_errors:
            print("\nConsole Error Details:")
            for err in console_errors:
                print(" -", err)

        print("======================================")

        # ======================================
        # Final Result
        # ======================================

        if (
            broken_css == 0
            and broken_js == 0
            and len(console_errors) == 0
        ):

            result["status"] = "PASS"

            print("✅ CSS / JS TEST PASSED")

        else:

            result["status"] = "FAIL"

            result["issue"] = (
                f"{broken_css} Broken CSS | "
                f"{broken_js} Broken JS | "
                f"{len(console_errors)} Console Errors"
            )

            result["possible_reason"] = (
                "Missing static files or frontend build issues."
            )

            result["recommendation"] = (
                "Verify CSS, JS imports and browser console."
            )

            result["developer_action"] = (
                "Fix broken assets and remove JS errors."
            )

            print("❌ CSS / JS TEST FAILED")

        print("======================================")
        print("CSS / JS TEST COMPLETED")
        print("======================================")

        return result

    except Exception as e:

        print("\n❌ CONTENT VALIDATION EXCEPTION")
        print(e)
        result["status"] = "FAIL"
        result["issue"] = str(e)
        return result


# =====================================
# Module 9 : Content Quality
# =====================================

def content_quality_test(page):

    # Initializing the dictionary with the fields you requested
    result = {
        "status": "PASS",
        "issue": "",
        "possible_reason": "",
        "recommendation": "",
        "developer_action": "",
        "desktop": {"status": ""},
        "tablet": {"status": ""},
        "mobile": {"status": "", "mobile_menu": False},
        "screenshots": [],
        "overflow_elements": 0,
        "overflow_details": [],
        "responsive_failed": 0,
        "responsive_details": [],
        "broken_content_images": 0,
        "empty_anchor_text": 0,
        "empty_anchor_details": [],
        "duplicate_paragraphs": 0,
        "duplicate_paragraph_details": [],
        "hidden_content": 0,
        "hidden_content_details": [],
        "encoding_issues": 0,
        "encoding_issue_details": []
    }

    try:

        # ======================================
        # 9.1 DESKTOP VIEW TEST
        # ======================================

        print("\n======================================")
        print("DESKTOP RESPONSIVE TEST")
        print("======================================")

        print("Setting Viewport : 1920 x 1080")

        page.set_viewport_size({
            "width": 1920,
            "height": 1080
        })

        page.reload()
        safe_network_idle(page)

        print("--------------------------------------")
        print("Checking Desktop Layout...")

        body_width = page.evaluate(
            "document.body.scrollWidth"
        )

        window_width = page.evaluate(
            "window.innerWidth"
        )

        print(f"Window Width : {window_width}")
        print(f"Body Width   : {body_width}")

        if body_width > window_width:

            print("❌ Horizontal Scroll Found")

            result["desktop"]["status"] = "FAIL"

            result["horizontal_scroll"] = True

        else:

            print("✅ No Horizontal Scroll")

            result["desktop"]["status"] = "PASS"

        print("--------------------------------------")

        desktop_ss = save_screenshot(
            page,
            "desktop_view.png"
        )

        print("📸 Desktop Screenshot Saved")

        result["screenshots"].append(desktop_ss)

        print("======================================")
        print("DESKTOP TEST COMPLETED")
        print("======================================")


        # ======================================
        # 9.2 TABLET VIEW TEST
        # ======================================

        print("\n======================================")
        print("TABLET RESPONSIVE TEST")
        print("======================================")

        print("Setting Viewport : 768 x 1024")

        page.set_viewport_size({
            "width": 768,
            "height": 1024
        })

        page.reload()
        safe_network_idle(page)

        print("--------------------------------------")
        print("Checking Tablet Layout...")

        body_width = page.evaluate(
            "document.body.scrollWidth"
        )

        window_width = page.evaluate(
            "window.innerWidth"
        )

        print(f"Window Width : {window_width}")
        print(f"Body Width   : {body_width}")

        if body_width > window_width:

            print("❌ Horizontal Scroll Found")

            result["tablet"]["status"] = "FAIL"

            result["horizontal_scroll"] = True

        else:

            print("✅ No Horizontal Scroll")

            result["tablet"]["status"] = "PASS"

        print("--------------------------------------")

        tablet_ss = save_screenshot(
            page,
            "tablet_view.png"
        )

        print("📸 Tablet Screenshot Saved")

        result["screenshots"].append(tablet_ss)

        print("======================================")
        print("TABLET TEST COMPLETED")
        print("======================================")


        # ======================================
        # 9.3 MOBILE VIEW TEST
        # ======================================

        print("\n======================================")
        print("MOBILE RESPONSIVE TEST")
        print("======================================")

        print("Setting Viewport : 375 x 812")

        page.set_viewport_size({
            "width": 375,
            "height": 812
        })

        page.reload()
        safe_network_idle(page)

        print("--------------------------------------")
        print("Checking Mobile Layout...")

        body_width = page.evaluate(
            "document.body.scrollWidth"
        )

        window_width = page.evaluate(
            "window.innerWidth"
        )

        print(f"Window Width : {window_width}")
        print(f"Body Width   : {body_width}")

        if body_width > window_width:

            print("❌ Horizontal Scroll Found")

            result["mobile"]["status"] = "FAIL"

            result["horizontal_scroll"] = True

        else:

            print("✅ No Horizontal Scroll")

            result["mobile"]["status"] = "PASS"

        # --------------------------------------
        # Mobile Navigation Check
        # --------------------------------------

        print("--------------------------------------")
        print("Checking Mobile Navigation...")

        menu_found = False

        menu_selectors = [
            "button[aria-label*=menu i]",
            "button[aria-label*=navigation i]",
            ".hamburger",
            ".menu-toggle",
            ".navbar-toggler",
            "#menu-toggle"
        ]

        for selector in menu_selectors:

            try:

                if page.locator(selector).count() > 0:

                    menu_found = True

                    print(f"✅ Mobile Menu Found : {selector}")

                    break

            except:
                pass

        if not menu_found:

            print("⚠ Mobile Menu Not Found")

        result["mobile"]["mobile_menu"] = menu_found

        # --------------------------------------
        # Screenshot
        # --------------------------------------

        mobile_ss = save_screenshot(
            page,
            "mobile_view.png"
        )

        print("📸 Mobile Screenshot Saved")

        result["screenshots"].append(mobile_ss)

        print("======================================")
        print("MOBILE TEST COMPLETED")
        print("======================================")


        # ======================================
        # 9.4 HORIZONTAL SCROLL TEST
        # ======================================

        print("\n======================================")
        print("HORIZONTAL SCROLL TEST")
        print("======================================")

        print("Scanning Entire Page...")

        overflow_elements = page.evaluate("""
        () => {
            let list = [];

            document.querySelectorAll("*").forEach(el => {

                if (el.scrollWidth > window.innerWidth) {

                    list.push({
                        tag: el.tagName,
                        id: el.id,
                        className: el.className,
                        width: el.scrollWidth
                    });

                }

            });

            return list;
        }
        """)

        print("--------------------------------------")

        if len(overflow_elements) == 0:

            print("✅ No Overflow Elements Found")

            result["overflow_elements"] = 0

        else:

            print(f"❌ Overflow Elements : {len(overflow_elements)}")

            result["overflow_elements"] = len(overflow_elements)

            result["overflow_details"] = overflow_elements

            for item in overflow_elements:

                print("--------------------------------")
                print(f"Tag    : {item['tag']}")
                print(f"ID     : {item['id']}")
                print(f"Class  : {item['className']}")
                print(f"Width  : {item['width']}")

        scroll_ss = save_screenshot(
            page,
            "horizontal_scroll_test.png"
        )

        print("📸 Horizontal Scroll Screenshot Saved")

        result["screenshots"].append(scroll_ss)

        print("======================================")
        print("HORIZONTAL SCROLL TEST COMPLETED")
        print("======================================")


        # ======================================
        # 9.5 RESPONSIVE ELEMENTS TEST
        # ======================================

        print("\n======================================")
        print("RESPONSIVE ELEMENTS TEST")
        print("======================================")

        responsive_failed = []
        elements = [

            ("img", "Images"),
            ("button", "Buttons"),
            ("input", "Inputs"),
            ("select", "Dropdowns"),
            ("textarea", "Textarea"),
            ("table", "Tables"),
            ("nav", "Navigation"),
            ("form", "Forms")

        ]

        for selector, name in elements:

            locator = page.locator(selector)

            count = locator.count()

            print("--------------------------------------")
            print(f"{name} Found : {count}")

            for i in range(count):

                try:

                    element = locator.nth(i)

                    visible = element.is_visible()

                    box = element.bounding_box()

                    if box:

                        width = box["width"]
                        height = box["height"]

                    else:

                        width = 0
                        height = 0

                    print(
                        f"{name} {i+1} | "
                        f"Visible={visible} | "
                        f"W={width:.0f} | "
                        f"H={height:.0f}"
                    )

                    if not visible or width <= 0 or height <= 0:

                        responsive_failed.append(
                            f"{name} {i+1}"
                        )

                except Exception:

                    responsive_failed.append(
                        f"{name} {i+1}"
                    )

        result["responsive_failed"] = len(responsive_failed)
        result["responsive_details"] = responsive_failed

        responsive_ss = save_screenshot(
            page,
            "responsive_elements_test.png"
        )

        result["screenshots"].append(responsive_ss)

        print("--------------------------------------")
        print(f"Responsive Failed : {len(responsive_failed)}")

        if responsive_failed:

            print("\nFailed Elements:")

            for item in responsive_failed:

                print(" -", item)

        print("======================================")
        print("RESPONSIVE ELEMENT TEST COMPLETED")
        print("======================================")


        # ======================================
        # 9.6 Broken Images Inside Content
        # ======================================

        print("\n======================================")
        print("BROKEN CONTENT IMAGES TEST")
        print("======================================")

        content_images = page.locator("article img, main img, section img").all()

        broken_content_images = []

        print(f"Images Inside Content : {len(content_images)}")

        for i, img in enumerate(content_images, start=1):

            print("--------------------------------")
            print(f"Checking Image {i}")

            try:

                src = img.get_attribute("src")

                print(f"SRC : {src}")

                if src:

                    response = page.request.get(src)

                    print(f"Status : {response.status}")

                    if response.status >= 400:

                        print("❌ Broken Content Image")

                        broken_content_images.append(src)

                    else:

                        print("✅ Image Working")

            except Exception:

                print("❌ Image Request Failed")

                broken_content_images.append(src)

        result["broken_content_images"] = len(broken_content_images)

        print("\n======================================")
        print(f"Broken Content Images : {len(broken_content_images)}")
        print("======================================")


        # ======================================
        # 9.7 EMPTY ANCHOR TEXT TEST
        # ======================================

        print("\n======================================")
        print("EMPTY ANCHOR TEXT TEST")
        print("======================================")

        anchors = page.locator("a").all()
        empty_links = []
        print(f"Total Anchor Tags : {len(anchors)}")

        for i, anchor in enumerate(anchors, start=1):

            print("--------------------------------")
            print(f"Checking Anchor : {i}")

            try:

                text = anchor.inner_text().strip()

                href = anchor.get_attribute("href")

                print(f"Text : {text}")
                print(f"Href : {href}")

                if text == "":

                    print("❌ Empty Anchor Text")

                    empty_links.append({

                        "href": href

                    })

                else:

                    print("✅ Anchor Text Available")

            except Exception as e:

                print("❌ Error")

                print(e)

        result["empty_anchor_text"] = len(empty_links)
        result["empty_anchor_details"] = empty_links

        print("\n======================================")
        print(f"Empty Anchor Text : {len(empty_links)}")
        print("======================================")


        # ======================================
        # 9.8 DUPLICATE PARAGRAPH TEST
        # ======================================

        print("\n======================================")
        print("DUPLICATE PARAGRAPH TEST")
        print("======================================")

        paragraphs = page.locator("p").all()

        duplicate_paragraphs = []

        all_text = []

        print(f"Total Paragraphs : {len(paragraphs)}")

        for i, para in enumerate(paragraphs, start=1):

            print("--------------------------------")
            print(f"Checking Paragraph : {i}")

            try:

                text = para.inner_text().strip()

                print(f"Length : {len(text)}")

                if text == "":

                    print("⚠ Empty Paragraph")
                    continue

                if text in all_text:

                    print("❌ Duplicate Paragraph Found")

                    duplicate_paragraphs.append({

                        "paragraph_no": i,

                        "text": text[:100]

                    })

                else:

                    print("✅ Unique Paragraph")

                    all_text.append(text)

            except Exception as e:

                print("❌ Error")
                print(e)

        result["duplicate_paragraphs"] = len(duplicate_paragraphs)

        result["duplicate_paragraph_details"] = duplicate_paragraphs

        print("\n======================================")
        print(f"Duplicate Paragraphs : {len(duplicate_paragraphs)}")
        print("======================================")


        # ======================================
        # 9.9 HIDDEN CONTENT TEST
        # ======================================

        print("\n======================================")
        print("HIDDEN CONTENT TEST")
        print("======================================")

        hidden_elements = []
        elements = page.locator("*").all()
        print(f"Total Elements : {len(elements)}")

        for i, element in enumerate(elements, start=1):

            try:

                tag = element.evaluate(
                    "el => el.tagName"
                )

                visible = element.is_visible()

                print("--------------------------------")
                print(f"Element : {i}")
                print(f"Tag     : {tag}")
                print(f"Visible : {visible}")

                if not visible:

                    print("❌ Hidden Element")

                    hidden_elements.append({

                        "tag": tag,

                        "index": i

                    })

                else:

                    print("✅ Visible")

            except Exception:

                pass

        result["hidden_content"] = len(hidden_elements)
        result["hidden_content_details"] = hidden_elements

        print("\n======================================")
        print(f"Hidden Elements : {len(hidden_elements)}")

        if hidden_elements:

            print("\nHidden Elements List")

            for item in hidden_elements:

                print(
                    f"Tag : {item['tag']} | "
                    f"Index : {item['index']}"
                )

        print("======================================")
        print("HIDDEN CONTENT TEST COMPLETED")
        print("======================================")


        # ======================================
        # 9.10 SPECIAL CHARACTER TEST
        # ======================================

        print("\n======================================")
        print("SPECIAL CHARACTER TEST")
        print("======================================")

        encoding_issues = []
        page_text = page.locator("body").inner_text()
        special_patterns = [

            "",
            "&nbsp;",
            "&amp;",
            "&#39;",
            "&lt;",
            "&gt;"

        ]

        print(f"Scanning {len(special_patterns)} Patterns...")

        for pattern in special_patterns:

            print("--------------------------------")
            print(f"Checking : {pattern}")

            if pattern in page_text:

                print("❌ Found")

                encoding_issues.append(pattern)

            else:

                print("✅ Not Found")

        result["encoding_issues"] = len(encoding_issues)
        result["encoding_issue_details"] = encoding_issues

        print("\n======================================")
        print(f"Encoding Issues : {len(encoding_issues)}")

        if encoding_issues:

            print("\nDetected Issues")

            for issue in encoding_issues:

                print(f" - {issue}")

        print("======================================")

        if len(encoding_issues) == 0:

            print("✅ SPECIAL CHARACTER TEST PASSED")

        else:

            result["status"] = "FAIL"

            result["issue"] = (
                f"{len(encoding_issues)} Encoding Issues Found"
            )

            result["possible_reason"] = (
                "HTML Encoding / Unicode issue."
            )

            result["recommendation"] = (
                "Replace encoded characters with proper UTF-8 text."
            )

            result["developer_action"] = (
                "Review frontend rendering and encoding."
            )

            print("❌ SPECIAL CHARACTER TEST FAILED")

        print("======================================")
        print("SPECIAL CHARACTER TEST COMPLETED")
        print("======================================")

        return result

    except Exception as e:
        
        print("\n❌ CONTENT QUALITY TEST EXCEPTION")
        print(e)

        result["status"] = "FAIL"
        result["issue"] = str(e)
        
        return result
    
    
    
# ----------------------------------------------------
# MODULE 10 : AUTHENTICATION TESTING
# ----------------------------------------------------

def authentication_test(page):

    print("========== AUTHENTICATION TEST START ==========\n")

    issues = []
    screenshots = []

    login_fields = []
    password_fields = []
    auth_buttons = []

    passed_features = 0
    failed_features = 0
    tested_features = 0

    # ------------------------------------------------
    # 10.1 PAGE CHECK
    # ------------------------------------------------

    print("[10.1] Checking current page...")

    try:

        print(f"Current URL : {page.url}")
        print("Page available")

    except Exception as e:

        print("❌ Page check failed")
        print(f"Error : {e}")

        return {
            "module": "Authentication Testing",
            "status": "FAIL",
            "login_fields": 0,
            "password_fields": 0,
            "auth_buttons": 0,
            "tested_features": 1,
            "passed_features": 0,
            "failed_features": 1,
            "module_score": 0,
            "issues": [str(e)],
            "recommendations": [
                "Verify website availability."
            ],
            "screenshots": [],
            "issue": str(e),
            "possible_reason": "Page could not be accessed.",
            "developer_action": "Review Playwright logs."
        }

    # ------------------------------------------------
    # 10.2 SEARCH LOGIN / EMAIL FIELDS
    # ------------------------------------------------

    print("\n[10.2] Searching authentication input fields...")

    try:

        inputs = page.locator(
            "input:visible"
        )

        total_inputs = inputs.count()

        print(
            f"Visible input fields : {total_inputs}"
        )

        for i in range(total_inputs):

            try:

                field = inputs.nth(i)

                input_type = (
                    field.get_attribute("type")
                    or ""
                ).lower()

                name = (
                    field.get_attribute("name")
                    or ""
                ).lower()

                placeholder = (
                    field.get_attribute("placeholder")
                    or ""
                ).lower()

                aria_label = (
                    field.get_attribute("aria-label")
                    or ""
                ).lower()

                combined = (
                    f"{input_type} "
                    f"{name} "
                    f"{placeholder} "
                    f"{aria_label}"
                )

                if (
                    input_type == "email"
                    or
                    "email" in combined
                    or
                    "username" in combined
                    or
                    "user name" in combined
                    or
                    "login" in combined
                ):

                    login_fields.append(i)

                    print(
                        f"Login field detected : "
                        f"{i + 1}"
                    )

            except Exception as e:

                print(
                    f"Input {i + 1} skipped : {e}"
                )

    except Exception as e:

        print("❌ Authentication input scan failed")
        print(f"Error : {e}")

        issues.append(
            f"Authentication input scan failed: {str(e)}"
        )

    # ------------------------------------------------
    # 10.3 SEARCH PASSWORD FIELDS
    # ------------------------------------------------

    print("\n[10.3] Searching password fields...")

    try:

        password_locator = page.locator(
            "input[type='password']:visible"
        )

        password_count = password_locator.count()

        print(
            f"Password fields found : "
            f"{password_count}"
        )

        for i in range(password_count):

            password_fields.append(i)

            print(
                f"Password field detected : "
                f"{i + 1}"
            )

    except Exception as e:

        print("❌ Password field scan failed")
        print(f"Error : {e}")

        issues.append(
            f"Password field scan failed: {str(e)}"
        )

    # ------------------------------------------------
    # 10.4 SEARCH AUTHENTICATION BUTTONS
    # ------------------------------------------------

    print(
        "\n[10.4] Searching login/sign-in buttons..."
    )

    try:

        buttons = page.locator(
            "button:visible, "
            "input[type='submit']:visible, "
            "input[type='button']:visible, "
            "a[role='button']:visible"
        )

        button_count = buttons.count()

        print(
            f"Visible buttons found : "
            f"{button_count}"
        )

        auth_keywords = [
            "login",
            "log in",
            "signin",
            "sign in",
            "authenticate",
            "continue",
            "my account",
            "account"
        ]

        for i in range(button_count):

            try:

                button = buttons.nth(i)

                text = button.inner_text(
                    timeout=3000
                ).strip()

                aria_label = (
                    button.get_attribute("aria-label")
                    or ""
                ).lower()

                title_attr = (
                    button.get_attribute("title")
                    or ""
                ).lower()

                href_attr = (
                    button.get_attribute("href")
                    or ""
                ).lower()

                class_attr = (
                    button.get_attribute("class")
                    or ""
                ).lower()

                text_lower = text.lower()

                combined = (
                    f"{text_lower} "
                    f"{aria_label} "
                    f"{title_attr} "
                    f"{class_attr}"
                )

                matched = any(
                    keyword in combined
                    for keyword in auth_keywords
                )

                if not matched and href_attr:

                    if (
                        "/login" in href_attr
                        or
                        "/signin" in href_attr
                        or
                        "/sign-in" in href_attr
                        or
                        "/account" in href_attr
                        or
                        "/my-account" in href_attr
                    ):

                        matched = True

                if matched:

                    label = (
                        text
                        or aria_label
                        or title_attr
                        or f"Auth Button {i + 1}"
                    )

                    auth_buttons.append({
                        "index": i,
                        "text": label
                    })

                    print(
                        f"Authentication button detected : "
                        f"{label}"
                    )

            except Exception as e:

                print(
                    f"Button {i + 1} skipped : {e}"
                )

    except Exception as e:

        print("❌ Authentication button scan failed")
        print(f"Error : {e}")

        issues.append(
            f"Authentication button scan failed: {str(e)}"
        )

    # ------------------------------------------------
    # 10.5 AUTHENTICATION FEATURE CHECK
    # ------------------------------------------------

    print(
        "\n[10.5] Checking authentication functionality..."
    )

    print(
        f"Login fields detected    : "
        f"{len(login_fields)}"
    )

    print(
        f"Password fields detected : "
        f"{len(password_fields)}"
    )

    print(
        f"Auth buttons detected    : "
        f"{len(auth_buttons)}"
    )

    # ------------------------------------------------
    # If no authentication UI exists
    # ------------------------------------------------

    if (
        len(login_fields) == 0
        and
        len(password_fields) == 0
        and
        len(auth_buttons) == 0
    ):

        print(
            "ℹ️ No authentication functionality "
            "detected on this page."
        )

        print(
            "Module treated as PASS because "
            "there was no authentication feature to test."
        )

        status = "PASS"
        module_score = 100

        recommendations = [
            "No authentication functionality detected.",
            "Module passed because there was no authentication feature available for testing."
        ]

        issue = ""

        possible_reason = (
            "The current webpage does not contain "
            "login or authentication controls."
        )

        developer_action = (
            "No action required unless this page "
            "is expected to provide authentication."
        )

    # ------------------------------------------------
    # Authentication UI exists
    # ------------------------------------------------

    else:

        # --------------------------------------------
        # Validate login fields
        # --------------------------------------------

        if len(login_fields) > 0:

            for index in login_fields:

                try:

                    field = inputs.nth(index)

                    visible = field.is_visible()
                    enabled = field.is_enabled()

                    print(
                        f"Login field {index + 1} "
                        f"| Visible : {visible} "
                        f"| Enabled : {enabled}"
                    )

                    tested_features += 1

                    if visible and enabled:

                        passed_features += 1

                        print(
                            "✅ Login field PASS"
                        )

                    else:

                        failed_features += 1

                        print(
                            "❌ Login field FAIL"
                        )

                        issues.append(
                            f"Login field {index + 1} is not usable."
                        )

                except Exception as e:

                    failed_features += 1
                    tested_features += 1

                    print(
                        f"❌ Login field validation failed : {e}"
                    )

                    issues.append(
                        f"Login field validation failed: {str(e)}"
                    )

        # --------------------------------------------
        # Validate password fields
        # --------------------------------------------

        if len(password_fields) > 0:

            for index in password_fields:

                try:

                    field = page.locator(
                        "input[type='password']:visible"
                    ).nth(index)

                    visible = field.is_visible()
                    enabled = field.is_enabled()

                    print(
                        f"Password field {index + 1} "
                        f"| Visible : {visible} "
                        f"| Enabled : {enabled}"
                    )

                    tested_features += 1

                    if visible and enabled:

                        passed_features += 1

                        print(
                            "✅ Password field PASS"
                        )

                    else:

                        failed_features += 1

                        print(
                            "❌ Password field FAIL"
                        )

                        issues.append(
                            f"Password field {index + 1} is not usable."
                        )

                except Exception as e:

                    failed_features += 1
                    tested_features += 1

                    print(
                        f"❌ Password field validation failed : {e}"
                    )

                    issues.append(
                        f"Password field validation failed: {str(e)}"
                    )

        # --------------------------------------------
        # Validate authentication buttons
        # --------------------------------------------

        if len(auth_buttons) > 0:

            for item in auth_buttons:

                try:

                    button = buttons.nth(
                        item["index"]
                    )

                    visible = button.is_visible()
                    enabled = button.is_enabled()

                    print(
                        f"Auth Button : {item['text']}"
                    )

                    print(
                        f"Visible : {visible}"
                    )

                    print(
                        f"Enabled : {enabled}"
                    )

                    tested_features += 1

                    if visible and enabled:

                        passed_features += 1

                        print(
                            "✅ Authentication button PASS"
                        )

                    else:

                        failed_features += 1

                        print(
                            "❌ Authentication button FAIL"
                        )

                        issues.append(
                            f"Authentication button "
                            f"{item['text']} is not usable."
                        )

                except Exception as e:

                    failed_features += 1
                    tested_features += 1

                    print(
                        f"❌ Authentication button validation failed : {e}"
                    )

                    issues.append(
                        "Authentication button validation failed: "
                        f"{str(e)}"
                    )

        # --------------------------------------------
        # Final authentication status
        # --------------------------------------------

        if failed_features > 0:

            status = "FAIL"

            module_score = int(
                (
                    passed_features /
                    tested_features
                ) * 100
            )

            recommendations = [
                "Fix authentication UI issues.",
                "Verify login and password fields.",
                "Verify authentication button functionality."
            ]

            issue = (
                f"{failed_features} authentication "
                "feature(s) failed."
            )

            possible_reason = (
                "One or more authentication controls "
                "were not usable."
            )

            developer_action = (
                "Review login fields, password fields "
                "and authentication controls."
            )

        else:

            status = "PASS"
            module_score = 100

            recommendations = [
                "Authentication controls are visible and usable."
            ]

            issue = ""
            possible_reason = ""
            developer_action = ""

    # ------------------------------------------------
    # 10.6 SCREENSHOT
    # ------------------------------------------------

    print(
        "\n[10.6] Taking screenshot..."
    )

    screenshot = (
        "screenshots/authentication_test.png"
    )

    try:

        page.screenshot(
            path=screenshot,
            full_page=True
        )

        screenshots.append(
            screenshot
        )

        print(
            f"Screenshot saved : {screenshot}"
        )

    except Exception as e:

        print(
            "Screenshot failed"
        )

        print(
            f"Error : {e}"
        )

    # ------------------------------------------------
    # 10.7 FINAL RESULT
    # ------------------------------------------------

    print("\n================================")

    print(
        f"Login Fields : "
        f"{len(login_fields)}"
    )

    print(
        f"Password Fields : "
        f"{len(password_fields)}"
    )

    print(
        f"Auth Buttons : "
        f"{len(auth_buttons)}"
    )

    print(
        f"Tested Features : "
        f"{tested_features}"
    )

    print(
        f"Passed Features : "
        f"{passed_features}"
    )

    print(
        f"Failed Features : "
        f"{failed_features}"
    )

    print(
        f"Module 10 Score : "
        f"{module_score}%"
    )

    print(
        f"Status : "
        f"{status}"
    )

    print("================================")

    print(
        "========== AUTHENTICATION TEST END ==========\n"
    )

    # ------------------------------------------------
    # RETURN RESULT
    # ------------------------------------------------

    return {

        "module": "Authentication Testing",

        "status": status,

        "login_fields": len(login_fields),

        "password_fields": len(password_fields),

        "auth_buttons": len(auth_buttons),

        "tested_features": tested_features,

        "passed_features": passed_features,

        "failed_features": failed_features,

        "module_score": module_score,

        "issues": issues,

        "recommendations": recommendations,

        "screenshots": screenshots,

        "issue": issue,

        "possible_reason": possible_reason,

        "developer_action": developer_action

    }

    
    
    
# ======================================
# MODULE 11 : SESSION & COOKIES TEST
# ======================================

def session_cookie_test(page):

    result = {
        "module": "Session & Cookies",
        "status": "PASS",
        "total_cookies": 0,
        "session_cookie_found": False,
        "secure_cookie": 0,
        "http_only_cookie": 0,
        "same_site_cookie": 0,
        "issues": [],
        "screenshots": []
    }

    try:

        print("\n======================================")
        print("SESSION & COOKIES TEST")
        print("======================================")

        cookies = page.context.cookies()

        result["total_cookies"] = len(cookies)

        print(f"Total Cookies : {len(cookies)}")

        for cookie in cookies:

            print("--------------------------------------")
            print(f"Name : {cookie['name']}")

            session_keywords = [
                "session",
                "sess",
                "sid",
                "auth",
                "token",
                "jwt",
                "__session",
                "__secure",
                "__host"
                ""
            ]

            name = cookie["name"].lower()

            if any(k in name for k in session_keywords):
                result["session_cookie_found"] = True

            if cookie.get("secure"):
                result["secure_cookie"] += 1

            if cookie.get("httpOnly"):
                result["http_only_cookie"] += 1

            if cookie.get("sameSite"):
                result["same_site_cookie"] += 1

        print("--------------------------------------")

        if result["total_cookies"] == 0:
            result["issues"].append("No Cookies Found")

        if result["secure_cookie"] == 0:
            result["issues"].append("Secure Cookie Missing")

        if result["http_only_cookie"] == 0:
            result["issues"].append("HttpOnly Cookie Missing")

        if result["same_site_cookie"] == 0:
            result["issues"].append("SameSite Cookie Missing")

        if len(result["issues"]) > 0:

            result["status"] = "FAIL"

            print("❌ Issues Found")

            for issue in result["issues"]:
                print("-", issue)

        else:

            print("✅ Session Cookies Valid")

        ss = save_screenshot(
            page,
            "session_cookie_test.png"
        )

        result["screenshots"].append(ss)

        print("======================================")
        print("SESSION & COOKIES TEST COMPLETED")
        print("======================================")

        return result

    except Exception as e:

        result["status"] = "FAIL"

        result["issues"].append(str(e))

        print(e)

        return result
    
# ======================================
# MODULE 12 : SEARCH FUNCTIONALITY
# ======================================

def search_functionality_test(page):

    result = {
        "module": "Search Functionality",
        "status": "PASS",
        "search_box_found": False,
        "search_button_found": False,
        "search_working": False,
        "results_found": 0,
        "issues": [],
        "screenshots": []
    }

    try:

        print("\n======================================")
        print("SEARCH FUNCTIONALITY TEST")
        print("======================================")

        page.wait_for_timeout(3000)
        safe_network_idle(page)

        # -------------------------------
        # Detect Search Box
        # -------------------------------

        search_box = page.locator("""
            input[type='search'],
            input[placeholder*='Search' i],
            input[name*='search' i],
            input[id*='search' i]
        """).first

        if search_box.count() == 0:

            result["status"] = "SKIPPED"
            result["issues"].append("Search Feature Not Available")

            ss = save_screenshot(
                page,
                "search_not_available.png"
            )

            result["screenshots"].append(ss)

            print("Search Feature Not Found")

            return result

        result["search_box_found"] = True

        print("Search Box Found")

        # -------------------------------
        # Detect Search Button
        # -------------------------------

        search_button = page.locator("""
            button[type='submit'],
            button[aria-label*='search' i],
            button:has-text('Search'),
            svg
        """).first

        if search_button.count() > 0:

            result["search_button_found"] = True

            print("Search Button Found")

        # -------------------------------
        # Search Test
        # -------------------------------

        test_keyword = "test"

        print(f"Searching : {test_keyword}")

        search_box.fill(test_keyword)

        if result["search_button_found"]:

            search_button.click(force=True)

        else:

            search_box.press("Enter")

        page.wait_for_timeout(4000)

        # -------------------------------
        # Detect Results
        # -------------------------------

        results = page.locator("""
            .result,
            .results,
            .search-result,
            article,
            .card,
            li
        """)

        total = results.count()

        result["results_found"] = total

        if total > 0:

            result["search_working"] = True

            print(f"Results Found : {total}")

        else:

            print("No Search Results Found")

            no_result = page.locator(
                "text=/no results|not found|nothing found/i"
            )

            if no_result.count() == 0:

                result["status"] = "FAIL"

                result["issues"].append(
                    "Search did not return results"
                )

        ss = save_screenshot(
            page,
            "search_test.png"
        )

        result["screenshots"].append(ss)

        print("======================================")
        print("SEARCH TEST COMPLETED")
        print("======================================")

        return result

    except Exception as e:

        result["status"] = "FAIL"

        result["issues"].append(str(e))

        try:

            ss = save_screenshot(
                page,
                "search_exception.png"
            )

            result["screenshots"].append(ss)

        except:
            pass

        return result  
   
# ======================================
# MODULE 13 : ACCESSIBILITY (WCAG)
# Part 1
# ======================================

from bs4 import BeautifulSoup


def accessibility_check(page):

    result = {
        "module": "Accessibility (WCAG)",
        "status": "PASS",

        "accessibility_score": 100,

        "total_images": 0,
        "images_without_alt": 0,

        "total_buttons": 0,
        "buttons_without_text": 0,

        "total_inputs": 0,
        "inputs_without_label": 0,

        "missing_h1": False,
        "missing_page_title": False,
        "missing_lang_attribute": False,

        "empty_links": 0,
        "duplicate_ids": 0,

        "issues": [],
        "recommendations": [],

        "screenshots": []
    }

    try:

        print("\n======================================")
        print("ACCESSIBILITY (WCAG) TEST")
        print("======================================")

        page.wait_for_timeout(3000)
        safe_network_idle(page)

        screenshot = save_screenshot(
            page,
            "accessibility_test.png"
        )

        result["screenshots"].append(
            screenshot
        )

        html = page.content()

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        # ----------------------------------
        # Collect Elements
        # ----------------------------------

        images = soup.find_all("img")

        buttons = soup.find_all("button")

        inputs = soup.find_all("input")

        labels = soup.find_all("label")

        links = soup.find_all("a")

        headings = soup.find_all("h1")

        result["total_images"] = len(images)

        result["total_buttons"] = len(buttons)

        result["total_inputs"] = len(inputs)

        print(f"Images   : {len(images)}")
        print(f"Buttons  : {len(buttons)}")
        print(f"Inputs   : {len(inputs)}")
        print(f"H1 Tags  : {len(headings)}")

        images_without_alt = 0
        buttons_without_text = 0
        inputs_without_label = 0
        empty_links = 0
        duplicate_ids = 0
        
       # ======================================
        # 13.1 IMAGE ALT CHECK
        # ======================================

        print("\n--------------------------------------")
        print("IMAGE ALT CHECK")
        print("--------------------------------------")

        for img in images:

            src = img.get("src", "")

            # Ignore tracking / analytics images
            if (
                "facebook.com/tr" in src
                or "adsct" in src
                or "analytics.twitter.com" in src
                or "doubleclick" in src
                or "googleads" in src
                or src.startswith("data:")
            ):
                continue

            print(f"Image : {src}")

            if not img.get("alt") or img.get("alt").strip() == "":

                images_without_alt += 1

                result["issues"].append(
                    f"Missing ALT : {src}"
                )
                
                print("❌ ALT Missing")

            else:

                print("✅ ALT Available")

        # ======================================
        # 13.2 BUTTON TEXT CHECK
        # ======================================

        print("\n--------------------------------------")
        print("BUTTON ACCESSIBILITY")
        print("--------------------------------------")

        for btn in buttons:

            text = btn.get_text(strip=True)

            aria = btn.get("aria-label")

            if text == "" and not aria:

                buttons_without_text += 1

                result["issues"].append(
                    "Button missing text/aria-label"
                )

                print("❌ Button Missing Text")

            else:

                print("✅ Button Accessible")


        # ======================================
        # 13.3 INPUT LABEL CHECK
        # ======================================

        print("\n--------------------------------------")
        print("INPUT LABEL CHECK")
        print("--------------------------------------")

        for field in inputs:

            field_id = field.get("id")

            placeholder = field.get("placeholder")

            aria = field.get("aria-label")

            has_label = False

            if field_id:

                lbl = soup.find(
                    "label",
                    attrs={"for": field_id}
                )

                if lbl:
                    has_label = True

            if not has_label and not placeholder and not aria:

                inputs_without_label += 1

                result["issues"].append(
                    f"Input missing label : {field.get('name')}"
                )

                print("❌ Input Missing Label")

            else:

                print("✅ Input Accessible")


        # ======================================
        # 13.4 EMPTY LINKS
        # ======================================

        print("\n--------------------------------------")
        print("EMPTY LINK CHECK")
        print("--------------------------------------")

        for link in links:

            href = link.get("href", "")

            text = link.get_text(strip=True)

            aria = link.get("aria-label")

            title = link.get("title")

            img = link.find("img")

            svg = link.find("svg")

            # Ignore navigation links
            if href in [
                "/",
                "/home",
                "/settings",
                "#"
            ]:
                continue

            if img or svg:
                continue

            if not text and not aria and not title:

                empty_links += 1

                result["issues"].append(
                    f"Empty Link : {href}"
                )

                print("❌ Empty Link")

            else:

                print("✅ Link Accessible")


        # ======================================
        # 13.5 DUPLICATE IDS
        # ======================================

        print("\n--------------------------------------")
        print("DUPLICATE ID CHECK")
        print("--------------------------------------")

        ids = []

        for tag in soup.find_all(True):

            tag_id = tag.get("id")

            if not tag_id:
                continue

            if tag_id in ids:

                duplicate_ids += 1

                result["issues"].append(
                    f"Duplicate ID : {tag_id}"
                )

                print(f"❌ Duplicate ID : {tag_id}")

            else:

                ids.append(tag_id)

        if duplicate_ids == 0:

            print("✅ No Duplicate IDs")


        # ======================================
        # 13.6 H1 CHECK
        # ======================================

        if len(headings) != 1:

            result["missing_h1"] = True

            result["issues"].append(
                "Page should contain exactly one H1"
            )

            print("❌ H1 Issue")

        else:

            print("✅ H1 Present")


        # ======================================
        # 13.7 PAGE TITLE
        # ======================================

        title = page.title().strip()

        if title == "":

            result["missing_page_title"] = True

            result["issues"].append(
                "Page title missing"
            )

            print("❌ Title Missing")

        else:

            print(f"✅ Title : {title}")


        # ======================================
        # 13.8 HTML LANG CHECK
        # ======================================

        html_tag = soup.find("html")

        if html_tag is None or not html_tag.get("lang"):

            result["missing_lang_attribute"] = True

            result["issues"].append(
                "HTML lang attribute missing"
            )

            print("❌ Lang Attribute Missing")

        else:

            print(
                f"✅ Lang : {html_tag.get('lang')}"
            )

        # ======================================
        # 13.9 SCORE CALCULATION
        # ======================================

        print("\n======================================")
        print("ACCESSIBILITY SCORE")
        print("======================================")

        score = 100

        score -= images_without_alt * 3
        score -= buttons_without_text * 10
        score -= inputs_without_label * 5
        score -= empty_links * 2
        score -= duplicate_ids * 5

        if result["missing_h1"]:
            score -= 5

        if result["missing_page_title"]:
            score -= 5

        if result["missing_lang_attribute"]:
            score -= 5

        if score < 0:
            score = 0

        result["accessibility_score"] = score

        result["images_without_alt"] = images_without_alt
        result["buttons_without_text"] = buttons_without_text
        result["inputs_without_label"] = inputs_without_label
        result["empty_links"] = empty_links
        result["duplicate_ids"] = duplicate_ids

        print(f"Accessibility Score : {score}%")

        # ======================================
        # 13.10 RECOMMENDATIONS
        # ======================================

        if images_without_alt > 0:
            result["recommendations"].append(
                "Add descriptive ALT text for every image."
            )

        if buttons_without_text > 0:
            result["recommendations"].append(
                "Provide visible text or aria-label for buttons."
            )

        if inputs_without_label > 0:
            result["recommendations"].append(
                "Associate every input with a label or aria-label."
            )

        if empty_links > 0:
            result["recommendations"].append(
                "Provide accessible text for hyperlinks."
            )

        if duplicate_ids > 0:
            result["recommendations"].append(
                "Remove duplicate HTML IDs."
            )

        if result["missing_h1"]:
            result["recommendations"].append(
                "Use exactly one H1 heading."
            )

        if result["missing_page_title"]:
            result["recommendations"].append(
                "Provide a meaningful page title."
            )

        if result["missing_lang_attribute"]:
            result["recommendations"].append(
                "Add the HTML lang attribute."
            )

        # ======================================
        # 13.11 FINAL STATUS
        # ======================================

        if len(result["issues"]) > 0:

            result["status"] = "FAIL"

            result["issue"] = (
                f"{len(result['issues'])} accessibility issue(s) found."
            )

            result["possible_reason"] = (
                "Website does not fully follow WCAG accessibility guidelines."
            )

            result["developer_action"] = (
                "Review accessibility issues and update frontend accordingly."
            )

            print("\n❌ ACCESSIBILITY TEST FAILED")

        else:

            result["status"] = "PASS"

            result["recommendations"].append(
                "No accessibility issues detected."
            )

            print("\n✅ ACCESSIBILITY TEST PASSED")

        print("======================================")
        print("ACCESSIBILITY TEST COMPLETED")
        print("======================================")

        return result

    except Exception as e:

        print("\n❌ ACCESSIBILITY MODULE EXCEPTION")
        print(e)

        result["status"] = "FAIL"

        result["issue"] = str(e)

        result["possible_reason"] = (
            "Unexpected exception while testing accessibility."
        )

        result["developer_action"] = (
            "Review accessibility module."
        )

        return result  
    
# ----------------------------------------------------
# MODULE 14 : SEO
# ----------------------------------------------------
def seo_test(page, url):

    print("========== SEO TEST START ==========\n")

    screenshots = []
    issues = []
    recommendations = []

    try:

        # ------------------------------------------------
        # 14.1 PAGE CHECK
        # ------------------------------------------------

        print("[14.1] Checking current page...")

        print(f"Current URL : {page.url}")
        print("✅ Page available")

        # ------------------------------------------------
        # 14.2 GET RENDERED HTML
        # ------------------------------------------------

        print("\n[14.2] Reading rendered HTML...")

        page.wait_for_timeout(3000)

        html = page.content()

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        # ------------------------------------------------
        # 14.3 ROBOTS.TXT
        # ------------------------------------------------

        print("\n[14.3] Checking robots.txt...")

        robots_exists = False
        robots_has_sitemap = False

        try:

            robots_url = (
                url.rstrip("/")
                + "/robots.txt"
            )

            robots_response = requests.get(
                robots_url,
                timeout=10
            )

            robots_exists = (
                robots_response.status_code == 200
            )

            if robots_exists:

                robots_has_sitemap = (
                    "sitemap:"
                    in robots_response.text.lower()
                )

            print(
                f"robots.txt : "
                f"{robots_response.status_code}"
            )

        except Exception as e:

            print(
                f"⚠️ robots.txt check failed : {e}"
            )

        # ------------------------------------------------
        # 14.4 SITEMAP
        # ------------------------------------------------

        print("\n[14.4] Checking sitemap.xml...")

        sitemap_exists = False

        try:

            sitemap_url = (
                url.rstrip("/")
                + "/sitemap.xml"
            )

            sitemap_response = requests.get(
                sitemap_url,
                timeout=10
            )

            sitemap_exists = (
                sitemap_response.status_code == 200
            )

            print(
                f"sitemap.xml : "
                f"{sitemap_response.status_code}"
            )

        except Exception as e:

            print(
                f"⚠️ Sitemap check failed : {e}"
            )

        # ------------------------------------------------
        # 14.5 TITLE
        # ------------------------------------------------

        print("\n[14.5] Checking title...")

        title_tag = soup.find("title")

        title = ""

        if title_tag:

            title = title_tag.get_text(
                strip=True
            )

        title_length = len(title)

        print(
            f"Title : {title}"
        )

        print(
            f"Title Length : {title_length}"
        )

        if not title:

            issues.append(
                "Missing page title."
            )

        # ------------------------------------------------
        # 14.6 META DESCRIPTION
        # ------------------------------------------------

        print(
            "\n[14.6] Checking meta description..."
        )

        meta_description = soup.find(
            "meta",
            attrs={
                "name": "description"
            }
        )

        description = ""

        if meta_description:

            description = meta_description.get(
                "content",
                ""
            ).strip()

        description_length = len(
            description
        )

        print(
            f"Meta Description Found : "
            f"{bool(description)}"
        )

        print(
            f"Description Length : "
            f"{description_length}"
        )

        if not description:

            issues.append(
                "Missing meta description."
            )

        # ------------------------------------------------
        # 14.7 CANONICAL
        # ------------------------------------------------

        print("\n[14.7] Checking canonical URL...")

        canonical = soup.find(
            "link",
            attrs={
                "rel": "canonical"
            }
        )

        canonical_exists = (
            canonical is not None
        )

        canonical_url = ""

        if canonical:

            canonical_url = canonical.get(
                "href",
                ""
            )

        print(
            f"Canonical : "
            f"{canonical_exists}"
        )

        # ------------------------------------------------
        # 14.8 VIEWPORT
        # ------------------------------------------------

        print(
            "\n[14.8] Checking mobile viewport..."
        )

        viewport = soup.find(
            "meta",
            attrs={
                "name": "viewport"
            }
        )

        mobile_friendly = False

        if viewport:

            viewport_content = viewport.get(
                "content",
                ""
            ).lower()

            mobile_friendly = (
                "width=device-width"
                in viewport_content
            )

        print(
            f"Mobile Viewport : "
            f"{mobile_friendly}"
        )

        # ------------------------------------------------
        # 14.9 LANGUAGE
        # ------------------------------------------------

        print("\n[14.9] Checking language tag...")

        html_tag = soup.find("html")

        language = ""

        if html_tag:

            language = html_tag.get(
                "lang",
                ""
            )

        lang_exists = bool(language)

        print(
            f"Language : "
            f"{language if language else 'Missing'}"
        )

        # ------------------------------------------------
        # 14.10 H1 / H2
        # ------------------------------------------------

        print("\n[14.10] Checking headings...")

        h1_tags = soup.find_all("h1")
        h2_tags = soup.find_all("h2")

        h1_count = len(h1_tags)
        h2_count = len(h2_tags)

        h1_text = [
            h.get_text(
                " ",
                strip=True
            )
            for h in h1_tags
        ]

        print(
            f"H1 Count : {h1_count}"
        )

        print(
            f"H2 Count : {h2_count}"
        )

        if h1_count == 0:

            issues.append(
                "No H1 heading found."
            )

        # ------------------------------------------------
        # 14.10b KEYWORDS
        # ------------------------------------------------

        print("\n[14.10b] Checking keywords...")

        meta_keywords_tag = soup.find(
            "meta",
            attrs={"name": "keywords"}
        )

        meta_keywords = []

        if meta_keywords_tag:

            raw_keywords = meta_keywords_tag.get(
                "content", ""
            )

            meta_keywords = [
                k.strip()
                for k in raw_keywords.split(",")
                if k.strip()
            ]

        text_soup = BeautifulSoup(
            html,
            "html.parser"
        )

        for tag in text_soup(["script", "style", "noscript"]):
            tag.decompose()

        body_text = text_soup.get_text(
            " ", strip=True
        ).lower()

        SEO_STOP_WORDS = {
            "the", "and", "for", "are", "but", "not", "you", "your",
            "with", "this", "that", "from", "have", "has", "our",
            "will", "can", "all", "was", "were", "who", "what",
            "when", "where", "why", "how", "into", "more", "than",
            "then", "them", "they", "their", "there", "here", "its",
            "about", "also", "get", "one", "use", "using", "each",
            "https", "http", "www", "com"
        }

        words = re.findall(r"[a-zA-Z]{4,}", body_text)

        filtered_words = [
            w for w in words
            if w not in SEO_STOP_WORDS
        ]

        keyword_counts = Counter(filtered_words)

        top_keywords = [
            {"keyword": kw, "count": count}
            for kw, count in keyword_counts.most_common(10)
        ]

        print(
            f"Top Keywords : "
            f"{[k['keyword'] for k in top_keywords]}"
        )

        title_lower = title.lower()
        description_lower = description.lower()
        h1_lower = " ".join(h1_text).lower()

        keyword_usage = [
            {
                "keyword": item["keyword"],
                "count": item["count"],
                "in_title": item["keyword"] in title_lower,
                "in_meta_description":
                    item["keyword"] in description_lower,
                "in_h1": item["keyword"] in h1_lower
            }
            for item in top_keywords[:5]
        ]

        if top_keywords and not any(
            k["in_title"] or k["in_h1"]
            for k in keyword_usage
        ):

            issues.append(
                "Top content keywords are not used in "
                "the title or H1 heading."
            )

            recommendations.append(
                "Include your primary keyword in the "
                "title and H1 heading."
            )

        # ------------------------------------------------
        # 14.11 FAVICON
        # ------------------------------------------------

        print("\n[14.11] Checking favicon...")

        favicon = soup.find(
            "link",
            rel=lambda value:
                value
                and
                any(
                    "icon" in str(v).lower()
                    for v in (
                        value
                        if isinstance(
                            value,
                            list
                        )
                        else [value]
                    )
                )
        )

        favicon_exists = (
            favicon is not None
        )

        print(
            f"Favicon : "
            f"{favicon_exists}"
        )

        # ------------------------------------------------
        # 14.12 OPEN GRAPH
        # ------------------------------------------------

        print(
            "\n[14.12] Checking Open Graph..."
        )

        og_title = soup.find(
            "meta",
            property="og:title"
        )

        og_description = soup.find(
            "meta",
            property="og:description"
        )

        og_image = soup.find(
            "meta",
            property="og:image"
        )

        og_url = soup.find(
            "meta",
            property="og:url"
        )

        og_type = soup.find(
            "meta",
            property="og:type"
        )

        open_graph = {

            "title": og_title is not None,

            "description":
                og_description is not None,

            "image":
                og_image is not None,

            "url":
                og_url is not None,

            "type":
                og_type is not None
        }

        print(
            f"OG Title : "
            f"{open_graph['title']}"
        )

        print(
            f"OG Description : "
            f"{open_graph['description']}"
        )

        print(
            f"OG Image : "
            f"{open_graph['image']}"
        )

        # ------------------------------------------------
        # 14.13 TWITTER CARD
        # ------------------------------------------------

        print(
            "\n[14.13] Checking Twitter Card..."
        )

        twitter_card = soup.find(
            "meta",
            attrs={
                "name": "twitter:card"
            }
        )

        twitter_exists = (
            twitter_card is not None
        )

        print(
            f"Twitter Card : "
            f"{twitter_exists}"
        )

        # ------------------------------------------------
        # 14.14 STRUCTURED DATA
        # ------------------------------------------------

        print(
            "\n[14.14] Checking structured data..."
        )

        schema_scripts = soup.find_all(
            "script",
            attrs={
                "type":
                "application/ld+json"
            }
        )

        structured_data = (
            len(schema_scripts) > 0
        )

        schema_types = []

        for script in schema_scripts:

            text = script.get_text(
                strip=True
            )

            if "Organization" in text:

                schema_types.append(
                    "Organization"
                )

            if "Product" in text:

                schema_types.append(
                    "Product"
                )

            if "Article" in text:

                schema_types.append(
                    "Article"
                )

            if "BreadcrumbList" in text:

                schema_types.append(
                    "BreadcrumbList"
                )

            if "FAQPage" in text:

                schema_types.append(
                    "FAQPage"
                )

        schema_types = list(
            set(schema_types)
        )

        print(
            f"Structured Data : "
            f"{structured_data}"
        )

        print(
            f"Schema Types : "
            f"{schema_types}"
        )

        # ------------------------------------------------
        # 14.15 IMAGE SEO
        # ------------------------------------------------

        print(
            "\n[14.15] Checking image SEO..."
        )

        images = soup.find_all("img")

        total_images = len(images)

        missing_alt = 0
        lazy_loaded = 0
        missing_dimensions = 0

        for img in images:

            if not img.get("alt"):

                missing_alt += 1

            if (
                img.get("loading") == "lazy"
                or img.get("data-src")
                or img.get("data-lazy-src")
            ):

                lazy_loaded += 1

            if (
                not img.get("width")
                or
                not img.get("height")
            ):

                missing_dimensions += 1

        print(
            f"Total Images : "
            f"{total_images}"
        )

        print(
            f"Missing Alt : "
            f"{missing_alt}"
        )

        print(
            f"Lazy Loaded : "
            f"{lazy_loaded}"
        )

        print(
            f"Missing Dimensions : "
            f"{missing_dimensions}"
        )

        if (
            total_images > 0
            and
            missing_alt > 0
        ):

            issues.append(
                f"{missing_alt} image(s) missing alt text."
            )

        # ------------------------------------------------
        # 14.16 SEO SCORE
        # ------------------------------------------------

        print(
            "\n[14.16] Calculating SEO score..."
        )

        score = 0

        if robots_exists:
            score += 10

        if sitemap_exists:
            score += 10

        if title:
            score += 10

        if description:
            score += 10

        if canonical_exists:
            score += 10

        if favicon_exists:
            score += 5

        if open_graph["title"]:
            score += 5

        if open_graph["description"]:
            score += 5

        if open_graph["image"]:
            score += 5

        if twitter_exists:
            score += 5

        if structured_data:
            score += 10

        if mobile_friendly:
            score += 5

        if lang_exists:
            score += 5

        if h1_count > 0:
            score += 5

        if (
            total_images == 0
            or
            missing_alt == 0
        ):

            score += 5

        score = min(
            score,
            100
        )

        # ------------------------------------------------
        # 14.17 SCREENSHOT
        # ------------------------------------------------

        print(
            "\n[14.17] Taking screenshot..."
        )

        screenshot = (
            "screenshots/seo_test.png"
        )

        try:

            page.screenshot(
                path=screenshot,
                full_page=True
            )

            screenshots.append(
                screenshot
            )

            print(
                f"Screenshot saved : "
                f"{screenshot}"
            )

        except Exception as e:

            print(
                f"⚠️ Screenshot failed : {e}"
            )

        # ------------------------------------------------
        # 14.18 FINAL STATUS
        # ------------------------------------------------

        if score >= 80:

            status = "PASS"

        elif score >= 60:

            status = "PARTIAL"

        else:

            status = "FAIL"

        recommendations = []

        if not robots_exists:

            recommendations.append(
                "Add robots.txt."
            )

        if not sitemap_exists:

            recommendations.append(
                "Add sitemap.xml."
            )

        if not title:

            recommendations.append(
                "Add a proper page title."
            )

        if not description:

            recommendations.append(
                "Add meta description."
            )

        if not canonical_exists:

            recommendations.append(
                "Add canonical URL."
            )

        if not mobile_friendly:

            recommendations.append(
                "Add mobile viewport configuration."
            )

        if not lang_exists:

            recommendations.append(
                "Add HTML language attribute."
            )

        if h1_count == 0:

            recommendations.append(
                "Add an H1 heading."
            )

        if (
            total_images > 0
            and
            missing_alt > 0
        ):

            recommendations.append(
                "Add alt text to images."
            )

        print("\n================================")
        print(
            f"SEO Score : {score}%"
        )
        print(
            f"Status : {status}"
        )
        print("================================")

        print(
            "========== SEO TEST END ==========\n"
        )

        return {

            "module": "SEO",

            "status": status,

            "seo_score": score,

            "robots_txt": robots_exists,

            "robots_has_sitemap":
                robots_has_sitemap,

            "sitemap_xml":
                sitemap_exists,

            "title": title,

            "title_length":
                title_length,

            "meta_description":
                bool(description),

            "description_length":
                description_length,

            "canonical":
                canonical_exists,

            "canonical_url":
                canonical_url,

            "favicon":
                favicon_exists,

            "open_graph":
                open_graph,

            "twitter_card":
                twitter_exists,

            "structured_data":
                structured_data,

            "schema_types":
                schema_types,

            "mobile_friendly":
                mobile_friendly,

            "language":
                language,

            "lang_tag":
                lang_exists,

            "h1_count":
                h1_count,

            "h2_count":
                h2_count,

            "h1_text":
                h1_text,

            "meta_keywords":
                meta_keywords,

            "top_keywords":
                top_keywords,

            "keyword_usage":
                keyword_usage,

            "image_seo": {

                "total_images":
                    total_images,

                "missing_alt":
                    missing_alt,

                "lazy_loaded":
                    lazy_loaded,

                "missing_dimensions":
                    missing_dimensions
            },

            "issues":
                issues,

            "recommendations":
                recommendations,

            "screenshots":
                screenshots,

            "issue":
                "; ".join(issues),

            "possible_reason":
                (
                    "One or more SEO checks "
                    "did not meet the expected criteria."
                    if issues
                    else ""
                ),

            "developer_action":
                (
                    "Review and fix the reported SEO issues."
                    if issues
                    else ""
                )
        }

    except Exception as e:

        print(
            "\n❌ SEO MODULE ERROR"
        )

        print(
            f"Error : {e}"
        )

        return {

            "module": "SEO",

            "status": "FAIL",

            "seo_score": 0,

            "issues": [
                str(e)
            ],

            "recommendations": [
                "Review SEO module execution."
            ],

            "screenshots":
                screenshots,

            "issue":
                str(e),

            "possible_reason":
                "SEO validation failed during execution.",

            "developer_action":
                "Review SEO test implementation."
        }
            
# ----------------------------------------------------
# MODULE 15 : RESPONSIVE DESIGN TEST
# ----------------------------------------------------

def responsive_test(page):

    print("========== RESPONSIVE TEST START ==========\n")

    devices = [
        {"name": "Desktop", "width": 1366, "height": 768},
        {"name": "Tablet", "width": 768, "height": 1024},
        {"name": "Mobile", "width": 390, "height": 844}
    ]

    issues = []
    screenshots = []
    passed = 0
    failed = 0

    for device in devices:

        print("--------------------------------")
        print(f"Testing : {device['name']}")

        page.set_viewport_size({
            "width": device["width"],
            "height": device["height"]
        })

        page.reload()
        safe_network_idle(page)

        screenshot = f"screenshots/{device['name'].lower()}_responsive.png"

        page.screenshot(
            path=screenshot,
            full_page=True
        )

        screenshots.append(screenshot)

        body = page.locator("body")
        box = body.bounding_box()

        if box:
            width = box["width"]
        else:
            width = device["width"]

        print(f"Viewport Width : {device['width']}")
        print(f"Body Width     : {width}")

        if width > device["width"] + 20:
            print("❌ Overflow Found")
            issues.append(
                f"{device['name']} layout overflow detected."
            )
            failed += 1
        else:
            print("✅ Responsive")
            passed += 1

    score = int((passed / len(devices)) * 100)
    status = "PASS"

    if issues:
        status = "FAIL"

    print("\n================================")
    print(f"Passed Devices : {passed}")
    print(f"Failed Devices : {failed}")
    print(f"Responsive Score : {score}%")
    print("================================")
    print("========== RESPONSIVE TEST END ==========\n")

    return {
        "module": "Responsive Design",
        "status": status,
        "responsive_score": score,
        "devices_tested": len(devices),
        "passed_devices": passed,
        "failed_devices": failed,
        "issues": issues,
        "recommendations": [
            "Ensure website adapts correctly to Desktop, Tablet and Mobile."
        ] if issues else [
            "Website is responsive across all tested devices."
        ],
        "screenshots": screenshots,
        "issue": (
            "Responsive issues found."
            if issues else
            "Responsive design verified."
        ),
        "possible_reason": (
            "CSS media queries or layout overflow."
            if issues else ""
        ),
        "developer_action": (
            "Review CSS responsiveness."
            if issues else ""
        )
    }     
  
# ----------------------------------------------------
# MODULE 18 : SECURITY HEADERS
# ----------------------------------------------------  
def security_headers_test(page, url):

    print("========== SECURITY HEADERS TEST START ==========\n")

    screenshots = []
    issues = []
    recommendations = []

    # ------------------------------------------------
    # 16.1 PAGE CHECK
    # ------------------------------------------------

    print("[16.1] Checking current page...")

    try:

        print(f"Current URL : {page.url}")
        print("✅ Page available")

    except Exception as e:

        print("❌ Page check failed")
        print(f"Error : {e}")

        return {
            "module": "Security Headers",
            "status": "FAIL",
            "security_score": 0,
            "total_headers": 0,
            "passed_headers": 0,
            "failed_headers": 0,
            "headers": {},
            "issues": [str(e)],
            "recommendations": [
                "Verify website availability."
            ],
            "screenshots": [],
            "issue": str(e),
            "possible_reason": "Page could not be accessed.",
            "developer_action": "Review Playwright logs."
        }

    # ------------------------------------------------
    # 16.2 GET RESPONSE HEADERS
    # ------------------------------------------------

    print("\n[16.2] Fetching HTTP response headers...")

    response = None

    try:

        response = page.request.get(
            url,
            timeout=60000
        )

        print(
            f"HTTP Status : {response.status}"
        )

        print("✅ Response received")

    except Exception as e:

        print("❌ Unable to fetch response headers")
        print(f"Error : {e}")

        return {
            "module": "Security Headers",
            "status": "FAIL",
            "security_score": 0,
            "total_headers": 0,
            "passed_headers": 0,
            "failed_headers": 0,
            "headers": {},
            "issues": [str(e)],
            "recommendations": [
                "Verify the website URL and server response."
            ],
            "screenshots": [],
            "issue": str(e),
            "possible_reason": "HTTP response could not be obtained.",
            "developer_action": "Check server/network configuration."
        }

    # ------------------------------------------------
    # 16.3 SECURITY HEADER CHECK
    # ------------------------------------------------

    print("\n[16.3] Checking security headers...")

    response_headers = response.headers

    # Convert headers to lowercase for reliable checking
    headers_lower = {
        key.lower(): value
        for key, value in response_headers.items()
    }

    security_headers = {

        "Strict-Transport-Security":
            "strict-transport-security",

        "Content-Security-Policy":
            "content-security-policy",

        "X-Content-Type-Options":
            "x-content-type-options",

        "X-Frame-Options":
            "x-frame-options",

        "Referrer-Policy":
            "referrer-policy",

        "Permissions-Policy":
            "permissions-policy"

    }

    passed_headers = 0
    failed_headers = 0

    header_results = {}

    for display_name, header_name in security_headers.items():

        value = headers_lower.get(
            header_name
        )

        print("--------------------------------")

        print(
            f"Header : {display_name}"
        )

        if value:

            print(
                f"Value  : {value}"
            )

            print("✅ PRESENT")

            passed_headers += 1

            header_results[display_name] = {
                "present": True,
                "value": value,
                "status": "PASS"
            }

        else:

            print("❌ MISSING")

            failed_headers += 1

            header_results[display_name] = {
                "present": False,
                "value": "",
                "status": "FAIL"
            }

            issues.append(
                f"{display_name} header is missing."
            )

            recommendations.append(
                f"Add {display_name} security header."
            )

    # ------------------------------------------------
    # 16.4 CALCULATE SCORE
    # ------------------------------------------------

    print(
        "\n[16.4] Calculating security header score..."
    )

    total_headers = len(
        security_headers
    )

    if total_headers > 0:

        security_score = int(
            (
                passed_headers /
                total_headers
            ) * 100
        )

    else:

        security_score = 0

    # ------------------------------------------------
    # 16.5 STATUS
    # ------------------------------------------------

    if passed_headers == total_headers:

        status = "PASS"

        issue = ""

        possible_reason = ""

        developer_action = ""

    elif passed_headers > 0:

        status = "PARTIAL"

        issue = (
            f"{failed_headers} security header(s) "
            "are missing."
        )

        possible_reason = (
            "Some recommended security headers "
            "are not configured on the server."
        )

        developer_action = (
            "Configure the missing security headers "
            "in the web server, reverse proxy, "
            "or application backend."
        )

    else:

        status = "FAIL"

        issue = (
            "All checked security headers are missing."
        )

        possible_reason = (
            "Security headers are not configured "
            "on the website response."
        )

        developer_action = (
            "Configure security headers on the "
            "server or reverse proxy."
        )

    # ------------------------------------------------
    # 16.6 SCREENSHOT
    # ------------------------------------------------

    print(
        "\n[16.6] Taking screenshot..."
    )

    screenshot = (
        "screenshots/security_headers_test.png"
    )

    try:

        page.screenshot(
            path=screenshot,
            full_page=True
        )

        screenshots.append(
            screenshot
        )

        print(
            f"✅ Screenshot saved : {screenshot}"
        )

    except Exception as e:

        print("⚠️ Screenshot failed")
        print(f"Error : {e}")

    # ------------------------------------------------
    # 16.7 FINAL RESULT
    # ------------------------------------------------

    print("\n================================")

    print(
        f"Total Headers  : {total_headers}"
    )

    print(
        f"Passed Headers : {passed_headers}"
    )

    print(
        f"Failed Headers : {failed_headers}"
    )

    print(
        f"Security Score : {security_score}%"
    )

    print(
        f"Status         : {status}"
    )

    print("================================")

    print(
        "========== SECURITY HEADERS TEST END ==========\n"
    )

    # ------------------------------------------------
    # RETURN RESULT
    # ------------------------------------------------

    return {

        "module": "Security Headers",

        "status": status,

        "security_score": security_score,

        "total_headers": total_headers,

        "passed_headers": passed_headers,

        "failed_headers": failed_headers,

        "headers": header_results,

        "issues": issues,

        "recommendations": recommendations,

        "screenshots": screenshots,

        "issue": issue,

        "possible_reason": possible_reason,

        "developer_action": developer_action

    }  
# ----------------------------------------------------
# MODULE 17 : CONSOLE ERROR DETECTION
# ----------------------------------------------------

def console_error_detection(page):

    print("========== CONSOLE ERROR TEST START ==========\n")

    console_errors = []

    def handle_console(msg):

        if msg.type == "error":
            console_errors.append(msg.text)

    page.on("console", handle_console)

    screenshot = "screenshots/console_error_test.png"

    try:
        page.reload(
            wait_until="domcontentloaded",
            timeout=DEFAULT_NAV_TIMEOUT
        )
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"⚠️ Console error module reload issue (continuing): {e}")

    try:
        page.screenshot(
            path=screenshot,
            full_page=True
        )
    except Exception as e:
        print(f"⚠️ Screenshot failed: {e}")

    if len(console_errors) == 0:

        status = "PASS"

        recommendations = [
            "No JavaScript console errors detected."
        ]

        issue = ""
        possible_reason = ""
        developer_action = ""

    else:

        status = "FAIL"

        recommendations = [
            "Fix JavaScript console errors."
        ]

        issue = f"{len(console_errors)} console error(s) found."

        possible_reason = (
            "JavaScript runtime errors or missing resources."
        )

        developer_action = (
            "Review browser console and fix JavaScript issues."
        )

    print("--------------------------------")
    print(f"Console Errors : {len(console_errors)}")

    for error in console_errors:
        print(error)

    print("--------------------------------")
    print(f"Status : {status}")

    print("========== CONSOLE ERROR TEST END ==========\n")

    return {

        "module": "Console Error Detection",

        "status": status,

        "console_error_count": len(console_errors),

        "issues": console_errors,

        "recommendations": recommendations,

        "screenshots": [
            screenshot
        ],

        "issue": issue,

        "possible_reason": possible_reason,

        "developer_action": developer_action

    } 
    
# ----------------------------------------------------
# MODULE 18 : BROKEN RESOURCES
# ----------------------------------------------------

def broken_resources_test(page):

    print("========== BROKEN RESOURCES TEST START ==========\n")

    broken_resources = []
    checked_resources = set()

    def handle_response(response):

        try:
            status = response.status

            # Check only failed HTTP resources
            if status >= 400:

                resource_url = response.url

                # Avoid duplicate resources
                if resource_url not in checked_resources:

                    checked_resources.add(resource_url)

                    broken_resources.append({
                        "url": resource_url,
                        "status_code": status,
                        "resource_type": response.request.resource_type
                    })

        except Exception:
            pass

    # Listen to all network responses
    page.on("response", handle_response)

    try:

        # Reload current website
        page.reload(
            wait_until="domcontentloaded",
            timeout=60000
        )

        # Give resources time to load
        page.wait_for_timeout(5000)

    except Exception as e:

        print("❌ Page loading error")
        print(e)

        broken_resources.append({
            "url": page.url,
            "status_code": 0,
            "resource_type": "page",
            "error": str(e)
        })

    screenshot = "screenshots/broken_resources_test.png"

    try:

        page.screenshot(
            path=screenshot,
            full_page=True
        )

    except Exception:
        screenshot = ""

    # -----------------------------------------
    # Result
    # -----------------------------------------

    broken_count = len(broken_resources)

    if broken_count == 0:

        status = "PASS"

        recommendations = [
            "No broken resources detected."
        ]

        issue = ""
        possible_reason = ""
        developer_action = ""

    else:

        status = "FAIL"

        recommendations = [
            "Fix broken images, CSS, JavaScript, or other failed resources."
        ]

        issue = (
            f"{broken_count} broken resource(s) detected."
        )

        possible_reason = (
            "Some website resources returned HTTP errors."
        )

        developer_action = (
            "Check the failed resource URLs and fix missing or invalid files."
        )

    # -----------------------------------------
    # Print Results
    # -----------------------------------------

    print("--------------------------------")
    print(f"Broken Resources : {broken_count}")

    for resource in broken_resources:

        print(
            f"❌ {resource.get('status_code')} "
            f"| {resource.get('resource_type')} "
            f"| {resource.get('url')}"
        )

    print("--------------------------------")
    print(f"Status : {status}")
    print("========== BROKEN RESOURCES TEST END ==========\n")

    return {

        "module": "Broken Resources",

        "status": status,

        "broken_resource_count": broken_count,

        "broken_resources": broken_resources,

        "issues": [
            resource.get("url", "")
            for resource in broken_resources
        ],

        "recommendations": recommendations,

        "screenshots": [
            screenshot
        ] if screenshot else [],

        "issue": issue,

        "possible_reason": possible_reason,

        "developer_action": developer_action

    }  
    

# ----------------------------------------------------
# MODULE 19 : ERROR PAGE (404) HANDLING TESTING
# ----------------------------------------------------

def error_page_test(page):

    print("========== ERROR PAGE (404) HANDLING TEST START ==========\n")

    issues = []
    recommendations = []
    screenshots = []

    tested_features = 0
    passed_features = 0
    failed_features = 0

    # ------------------------------------------------
    # 19.1 PAGE CHECK
    # ------------------------------------------------

    print("[19.1] Checking current page...")

    try:

        base_url = page.url

        print(f"Current URL : {base_url}")
        print("Page available")

    except Exception as e:

        print("❌ Page check failed")
        print(f"Error : {e}")

        return {

            "module": "Error Page (404) Handling",

            "status": "FAIL",

            "issue": str(e),

            "issues": [str(e)],

            "possible_reason": "Could not read the current page URL.",

            "recommendations": [
                "Retry the test once the page has finished loading."
            ],

            "developer_action": "Check Playwright execution logs for this module.",

            "module_score": 0,

            "screenshots": []

        }

    # ------------------------------------------------
    # 19.2 BUILD A NON-EXISTENT URL
    # ------------------------------------------------

    print(
        "\n[19.2] Building a non-existent page URL..."
    )

    random_slug = (
        "qa-check-page-not-found-"
        + str(int(time.time()))
    )

    broken_url = urljoin(
        base_url,
        "/" + random_slug
    )

    print(
        f"Testing URL : {broken_url}"
    )

    # ------------------------------------------------
    # 19.3 NAVIGATE TO THE NON-EXISTENT PAGE
    # ------------------------------------------------

    print(
        "\n[19.3] Navigating to the non-existent page..."
    )

    status_code = None
    navigation_error = None

    try:

        response = page.goto(
            broken_url,
            wait_until="domcontentloaded",
            timeout=DEFAULT_NAV_TIMEOUT
        )

        if response is not None:
            status_code = response.status

        safe_network_idle(page)

        print(
            f"HTTP Status Code : {status_code}"
        )

    except Exception as e:

        navigation_error = str(e)

        print("❌ Navigation to non-existent page failed")
        print(f"Error : {e}")

    # ------------------------------------------------
    # 19.4 CHECK HTTP STATUS CODE
    # ------------------------------------------------

    print(
        "\n[19.4] Checking HTTP status code..."
    )

    tested_features += 1

    if navigation_error:

        failed_features += 1

        issues.append(
            f"Could not load a non-existent URL to test "
            f"error handling ({navigation_error})."
        )

    elif status_code in (404, 410):

        passed_features += 1

        print(
            f"Server correctly returned status {status_code} "
            f"for a missing page."
        )

    elif status_code == 200:

        failed_features += 1

        issues.append(
            "The server returns HTTP 200 for a non-existent page "
            "instead of 404 (a 'soft 404')."
        )

    else:

        failed_features += 1

        issues.append(
            f"Unexpected status code {status_code} returned "
            f"for a non-existent page."
        )

    # ------------------------------------------------
    # 19.5 CHECK FOR A CUSTOM (BRANDED) ERROR PAGE
    # ------------------------------------------------

    print(
        "\n[19.5] Checking for a custom error page..."
    )

    tested_features += 1

    generic_browser_error_markers = [
        "this site can’t be reached",
        "this site can't be reached",
        "err_",
        "http error 404",
        "404 not found",
        "nginx",
        "apache tomcat",
    ]

    page_text = ""
    has_custom_error_page = False

    try:

        page_text = page.inner_text("body").lower()

        looks_like_generic_error = any(
            marker in page_text
            for marker in generic_browser_error_markers
            if marker in ("err_", "nginx", "apache tomcat")
        )

        has_helpful_wording = any(
            keyword in page_text
            for keyword in [
                "page not found",
                "we can't find",
                "we can’t find",
                "page you are looking for",
                "doesn't exist",
                "does not exist",
                "not found",
                "404",
            ]
        )

        has_custom_error_page = (
            has_helpful_wording
            and not looks_like_generic_error
            and not navigation_error
        )

        if has_custom_error_page:

            passed_features += 1

            print("Custom / branded error page detected.")

        else:

            failed_features += 1

            issues.append(
                "No clear custom error page content was detected "
                "for the missing page."
            )

    except Exception as e:

        failed_features += 1

        issues.append(
            f"Could not inspect error page content ({e})."
        )

    # ------------------------------------------------
    # 19.6 CHECK FOR A WAY BACK TO THE SITE
    # ------------------------------------------------

    print(
        "\n[19.6] Checking for a link back to the site..."
    )

    tested_features += 1

    has_return_link = False

    try:

        return_link_keywords = [
            "home",
            "go back",
            "back to",
            "homepage",
            "return",
        ]

        links = page.locator("a")
        total_links = links.count()

        for i in range(min(total_links, 50)):

            try:

                link_text = (
                    links.nth(i).inner_text(timeout=2000)
                    or ""
                ).strip().lower()

            except Exception:
                continue

            if any(
                keyword in link_text
                for keyword in return_link_keywords
            ):
                has_return_link = True
                break

        if has_return_link:

            passed_features += 1

            print("Found a link that leads back to the site.")

        else:

            failed_features += 1

            issues.append(
                "The error page does not offer an obvious link "
                "back to the homepage."
            )

    except Exception as e:

        failed_features += 1

        issues.append(
            f"Could not check for a return link ({e})."
        )

    # ------------------------------------------------
    # 19.7 RETURN TO THE ORIGINAL PAGE
    # ------------------------------------------------

    print(
        "\n[19.7] Returning to the original page..."
    )

    try:

        safe_goto(page, base_url)

    except Exception as e:

        print(
            f"Could not return to the original page : {e}"
        )

    # ------------------------------------------------
    # 19.8 SCREENSHOT
    # ------------------------------------------------

    print(
        "\n[19.8] Taking screenshot..."
    )

    screenshot = (
        "screenshots/error_page_test.png"
    )

    try:

        page.screenshot(
            path=screenshot,
            full_page=True
        )

        screenshots.append(
            screenshot
        )

        print(
            f"Screenshot saved : {screenshot}"
        )

    except Exception as e:

        print(
            "Screenshot failed"
        )

        print(
            f"Error : {e}"
        )

    # ------------------------------------------------
    # 19.9 CALCULATE RESULTS
    # ------------------------------------------------

    print(
        "\n[19.9] Calculating results..."
    )

    if tested_features > 0:

        module_score = int(
            (passed_features / tested_features) * 100
        )

    else:

        module_score = 0

    if module_score == 100:

        status = "PASS"

        recommendations = [
            "Error page handling looks good : the site returns a "
            "proper 404, shows helpful content, and links back home."
        ]

        issue = ""
        possible_reason = ""
        developer_action = ""

    else:

        status = "FAIL"

        recommendations = [
            "Return an HTTP 404 status for missing pages.",
            "Show a friendly, branded error page instead of a "
            "generic server error.",
            "Add a clear link back to the homepage on the error page."
        ]

        issue = (
            f"{failed_features} of {tested_features} error-page "
            f"check(s) failed."
        )

        possible_reason = (
            "The website does not fully implement custom error "
            "(404) page handling."
        )

        developer_action = (
            "Review how the server and front-end handle unknown "
            "URLs and improve the 404 experience."
        )

    print(
        "--------------------------------"
    )

    print(
        f"Tested   : {tested_features}"
    )

    print(
        f"Passed   : {passed_features}"
    )

    print(
        f"Failed   : {failed_features}"
    )

    print(
        f"Module 19 Score : "
        f"{module_score}%"
    )

    print(
        f"Status : "
        f"{status}"
    )

    print("--------------------------------")

    print(
        "========== ERROR PAGE (404) HANDLING TEST END ==========\n"
    )

    # ------------------------------------------------
    # RETURN RESULT
    # ------------------------------------------------

    return {

        "module": "Error Page (404) Handling",

        "status": status,

        "status_code": status_code,

        "has_custom_error_page": has_custom_error_page,

        "has_return_link": has_return_link,

        "tested_features": tested_features,

        "passed_features": passed_features,

        "failed_features": failed_features,

        "module_score": module_score,

        "issues": issues,

        "recommendations": recommendations,

        "screenshots": screenshots,

        "issue": issue,

        "possible_reason": possible_reason,

        "developer_action": developer_action

    }

# ----------------------------------------------------
# MODULE 20 : API VALIDATION TESTING
# ----------------------------------------------------

def api_validation_test(page):

    print("\n========== API VALIDATION TEST START ==========\n")

    api_requests = []
    failed_requests = []
    auth_requests = []
    screenshots = []

    # ------------------------------------------------
    # 20.1 PAGE CHECK
    # ------------------------------------------------

    print("[20.1] Checking current page...")

    try:

        current_url = page.url

        print(f"Current URL : {current_url}")
        print("Page available")

    except Exception as e:

        print("❌ Page check failed")
        print(f"Error : {e}")

        return {
            "module": "API Validation",
            "status": "FAIL",

            "api_count": 0,
            "api_passed": 0,
            "api_failed": 1,
            "api_score": 0,

            "api_requests": [],
            "failed_requests": [],
            "auth_requests": [],

            "tested_features": 1,
            "passed_features": 0,
            "failed_features": 1,

            "issues": [
                str(e)
            ],

            "recommendations": [
                "Verify website availability."
            ],

            "screenshots": [],

            "issue": str(e),

            "possible_reason":
                "Page could not be accessed.",

            "developer_action":
                "Review Playwright page loading logs."
        }

    # ------------------------------------------------
    # 20.2 API RESPONSE MONITORING
    # ------------------------------------------------

    print(
        "\n[20.2] Starting API/network monitoring..."
    )

    THIRD_PARTY_TRACKER_DOMAINS = [
        "google-analytics.com",
        "googletagmanager.com",
        "doubleclick.net",
        "googleadservices.com",
        "googlesyndication.com",
        "facebook.com/tr",
        "connect.facebook.net",
        "analytics.twitter.com",
        "hotjar.com",
        "sentry.io",
        "clarity.ms",
        "segment.com",
        "mixpanel.com",
        "intercom.io",
        "amplitude.com",
        "cdn.segment.com",
        "adsct"
    ]

    def handle_response(response):

        try:

            request = response.request

            resource_type = request.resource_type

            # Only API-like requests
            if resource_type not in [
                "xhr",
                "fetch"
            ]:
                return

            # Skip third-party tracking/analytics calls - these are
            # not the website's own API and shouldn't count toward
            # its API health score.
            response_url_lower = response.url.lower()

            if any(
                domain in response_url_lower
                for domain in THIRD_PARTY_TRACKER_DOMAINS
            ):
                return

            status_code = response.status

            api_data = {

                "method":
                    request.method,

                "url":
                    response.url,

                "status":
                    status_code,

                "resource_type":
                    resource_type
            }

            api_requests.append(
                api_data
            )

            print("--------------------------------")
            print("📡 API RESPONSE DETECTED")

            print(
                f"Method        : "
                f"{request.method}"
            )

            print(
                f"URL           : "
                f"{response.url}"
            )

            print(
                f"Resource Type : "
                f"{resource_type}"
            )

            print(
                f"Status        : "
                f"{status_code}"
            )

            # ----------------------------------------
            # Authentication responses
            # ----------------------------------------

            if status_code in [
                401,
                403
            ]:

                auth_requests.append({

                    "method":
                        request.method,

                    "url":
                        response.url,

                    "status":
                        status_code
                })

                print(
                    "⚠️ Authentication response detected"
                )

            # ----------------------------------------
            # Normal API validation
            # ----------------------------------------

            if (
                status_code is not None
                and
                200 <= status_code < 400
            ):

                print(
                    "✅ API RESPONSE PASS"
                )

            elif status_code in [
                401,
                403
            ]:

                print(
                    "⚠️ AUTHENTICATION RESPONSE"
                )

            else:

                print(
                    "❌ API RESPONSE FAIL"
                )

        except Exception as e:

            print(
                "⚠️ API response processing error"
            )

            print(
                f"Error : {e}"
            )

    # Attach listener BEFORE reload
    page.on(
        "response",
        handle_response
    )

    # ------------------------------------------------
    # 20.3 RELOAD PAGE
    # ------------------------------------------------

    print(
        "\n[20.3] Reloading page..."
    )

    try:

        page.reload(
            wait_until="domcontentloaded",
            timeout=60000
        )

        print(
            "Page reloaded"
        )

    except Exception as e:

        print(
            "⚠️ Page reload warning"
        )

        print(
            f"Error : {e}"
        )

    # ------------------------------------------------
    # 20.4 WAIT FOR API RESPONSES
    # ------------------------------------------------

    print(
        "\n[20.4] Waiting for API responses..."
    )

    try:

        page.wait_for_timeout(
            5000
        )

    except Exception as e:

        print(
            "⚠️ API wait warning"
        )

        print(
            f"Error : {e}"
        )

    print(
        f"Captured API responses : "
        f"{len(api_requests)}"
    )

    # ------------------------------------------------
    # 20.5 REMOVE DUPLICATES
    # ------------------------------------------------

    print(
        "\n[20.5] Removing duplicate API entries..."
    )

    unique_requests = []

    seen = set()

    for request in api_requests:

        key = (
            request["method"],
            request["url"],
            request["status"]
        )

        if key not in seen:

            seen.add(key)

            unique_requests.append(
                request
            )

    api_requests = unique_requests

    print(
        f"Unique API requests : "
        f"{len(api_requests)}"
    )

    # ------------------------------------------------
    # 20.6 CALCULATE API RESULTS
    # ------------------------------------------------

    print(
        "\n[20.6] Calculating API results..."
    )

    api_passed = 0
    api_failed = 0

    for request in api_requests:

        status_code = request["status"]

        # --------------------------------------------
        # Successful API
        # --------------------------------------------

        if (
            status_code is not None
            and
            200 <= status_code < 400
        ):

            api_passed += 1

        # --------------------------------------------
        # 401 / 403
        # --------------------------------------------
        # These are authentication responses.
        # Do NOT automatically count them as API failure.
        # --------------------------------------------

        elif status_code in [
            401,
            403
        ]:

            continue

        # --------------------------------------------
        # Other 4xx / 5xx
        # --------------------------------------------

        else:

            api_failed += 1

            failed_requests.append({

                "method":
                    request["method"],

                "url":
                    request["url"],

                "status":
                    status_code
            })

    api_count = len(
        api_requests
    )

    print("--------------------------------")

    print(
        f"Total APIs Detected : "
        f"{api_count}"
    )

    print(
        f"APIs Passed : "
        f"{api_passed}"
    )

    print(
        f"APIs Failed : "
        f"{api_failed}"
    )

    print("--------------------------------")

    # ------------------------------------------------
    # 20.7 DETERMINE STATUS
    # ------------------------------------------------

    issues = []

    recommendations = []

    issue = ""

    possible_reason = ""

    developer_action = ""

    # ------------------------------------------------
    # NO API DETECTED
    # ------------------------------------------------

    if api_count == 0:

        status = "NOT_AVAILABLE"

        api_score = None

        recommendations = [

            "No XHR or Fetch API requests were detected.",

            "API validation is not applicable to "
            "the current webpage during this test."
        ]

        possible_reason = (

            "The webpage did not make any XHR or "
            "Fetch requests during the tested page load."
        )

        developer_action = (

            "No action required unless the webpage "
            "is expected to communicate with backend APIs."
        )

        print(
            "No XHR/Fetch API requests detected."
        )

    # ------------------------------------------------
    # API FAILURE
    # ------------------------------------------------

    elif api_failed > 0:

        status = "FAIL"

        api_score = int(

            (
                api_passed /
                api_count
            ) * 100

        )

        issues.append(

            f"{api_failed} API request(s) "
            "returned unexpected error status."
        )

        recommendations = [

            "Fix failed API requests.",

            "Verify API endpoints and HTTP status codes.",

            "Review backend/server logs.",

            "Verify frontend API integration."
        ]

        issue = (

            f"{api_failed} API request(s) "
            "failed."
        )

        possible_reason = (

            "One or more API endpoints returned "
            "unexpected 4xx or 5xx responses."
        )

        developer_action = (

            "Review the failed API endpoints, "
            "backend logs, request parameters and "
            "server responses."
        )

    # ------------------------------------------------
    # API PASS
    # ------------------------------------------------

    else:

        status = "PASS"

        api_score = 100

        recommendations = [

            "All detected API requests returned "
            "successful responses."
        ]

        print(
            "All detected APIs passed."
        )

    # ------------------------------------------------
    # 20.8 API DETAILS
    # ------------------------------------------------

    print(
        "\n[20.8] API details..."
    )

    if api_count == 0:

        print(
            "No API requests detected."
        )

    else:

        for index, request in enumerate(
            api_requests,
            start=1
        ):

            print("--------------------------------")

            print(
                f"API #{index}"
            )

            print(
                f"Method        : "
                f"{request['method']}"
            )

            print(
                f"URL           : "
                f"{request['url']}"
            )

            print(
                f"Resource Type : "
                f"{request['resource_type']}"
            )

            print(
                f"Status        : "
                f"{request['status']}"
            )

            if (
                request["status"] is not None
                and
                200 <= request["status"] < 400
            ):

                print(
                    "✅ API PASS"
                )

            elif request["status"] in [
                401,
                403
            ]:

                print(
                    "⚠️ AUTHENTICATION RESPONSE"
                )

            else:

                print(
                    "❌ API FAIL"
                )

    # ------------------------------------------------
    # 20.9 API FAILURE DETAILS
    # ------------------------------------------------

    print(
        "\n[20.9] API failure details..."
    )

    if failed_requests:

        for failure in failed_requests:

            print("--------------------------------")

            print(
                f"Method : "
                f"{failure['method']}"
            )

            print(
                f"URL : "
                f"{failure['url']}"
            )

            print(
                f"Status : "
                f"{failure['status']}"
            )

    else:

        print(
            "No unexpected failed API requests detected."
        )

    # ------------------------------------------------
    # 20.9A AUTHENTICATION DETAILS
    # ------------------------------------------------

    print(
        "\n[20.9A] Authentication response details..."
    )

    if auth_requests:

        for auth in auth_requests:

            print("--------------------------------")

            print(
                f"Method : "
                f"{auth['method']}"
            )

            print(
                f"URL : "
                f"{auth['url']}"
            )

            print(
                f"Status : "
                f"{auth['status']}"
            )

    else:

        print(
            "No 401/403 authentication responses detected."
        )

    # ------------------------------------------------
    # 20.10 SCREENSHOT
    # ------------------------------------------------

    print(
        "\n[20.10] Taking screenshot..."
    )

    screenshot = (
        "screenshots/api_validation_test.png"
    )

    try:

        page.screenshot(
            path=screenshot,
            full_page=True
        )

        screenshots.append(
            screenshot
        )

        print(
            f"Screenshot saved : "
            f"{screenshot}"
        )

    except Exception as e:

        print(
            "Screenshot failed"
        )

        print(
            f"Error : {e}"
        )

    # ------------------------------------------------
    # 20.11 FINAL SUMMARY
    # ------------------------------------------------

    print(
        "\n================================"
    )

    print(
        f"API Count   : "
        f"{api_count}"
    )

    print(
        f"API Passed  : "
        f"{api_passed}"
    )

    print(
        f"API Failed  : "
        f"{api_failed}"
    )

    if api_score is None:

        print(
            "API Score   : N/A"
        )

    else:

        print(
            f"API Score   : "
            f"{api_score}%"
        )

    print(
        f"Status      : "
        f"{status}"
    )

    print(
        "================================"
    )

    print(
        "========== API VALIDATION TEST END ==========\n"
    )

    # ------------------------------------------------
    # RETURN RESULT
    # ------------------------------------------------

    return {

        "module":
            "API Validation",

        "status":
            status,

        "api_count":
            api_count,

        "api_passed":
            api_passed,

        "api_failed":
            api_failed,

        "api_score":
            api_score,

        "api_requests":
            api_requests,

        "failed_requests":
            failed_requests,

        "auth_requests":
            auth_requests,

        "issues":
            issues,

        "recommendations":
            recommendations,

        "screenshots":
            screenshots,

        "issue":
            issue,

        "possible_reason":
            possible_reason,

        "developer_action":
            developer_action
    }   

# ----------------------------------------------------
# MODULE 21 : BROWSER COMPATIBILITY
# ----------------------------------------------------

def browser_compatibility_test(playwright, url):

    print("========== BROWSER COMPATIBILITY TEST START ==========\n")

    browsers = [
        ("Chrome", playwright.chromium),
        ("Firefox", playwright.firefox),
        ("Edge", playwright.chromium)
    ]

    passed = 0
    failed = 0

    screenshots = []
    issues = []

    # ------------------------------------------------
    # 21.1 START TEST
    # ------------------------------------------------

    print("[21.1] Starting browser compatibility testing...")
    print(f"Website URL : {url}\n")

    # ------------------------------------------------
    # 21.2 TEST EACH BROWSER
    # ------------------------------------------------

    for browser_name, browser_type in browsers:

        print("--------------------------------")
        print(f"Testing Browser : {browser_name}")

        browser = None
        page = None

        try:

            # ----------------------------------------
            # Launch browser
            # ----------------------------------------

            print(
                f"[21.2] Launching {browser_name}..."
            )

            browser = browser_type.launch(
                headless=True
            )

            print(
                f"✅ {browser_name} launched"
            )

            # ----------------------------------------
            # Create page
            # ----------------------------------------

            page = browser.new_page(
                viewport={
                    "width": 1366,
                    "height": 768
                }
            )

            print(
                f"[21.3] Opening website in {browser_name}..."
            )

            # IMPORTANT:
            # Use domcontentloaded instead of networkidle
            # to avoid unnecessary timeout.

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            print(
                f"✅ Page opened in {browser_name}"
            )

            # ----------------------------------------
            # Wait for rendering
            # ----------------------------------------

            page.wait_for_timeout(
               6000
            )

            # ----------------------------------------
            # Page title
            # ----------------------------------------

            title = page.title()

            print(
                f"Page Title : {title}"
            )

            # ----------------------------------------
            # Current URL
            # ----------------------------------------

            current_url = page.url

            print(
                f"Final URL : {current_url}"
            )

            # ----------------------------------------
            # Body check
            # ----------------------------------------

            body = page.locator(
                "body"
            )

            body_visible = body.is_visible()

            print(
                f"Body Visible : {body_visible}"
            )

            # ----------------------------------------
            # Screenshot
            # ----------------------------------------

            screenshot = (
                f"screenshots/"
                f"{browser_name.lower()}"
                f"_compatibility_test.png"
            )

            print(
                f"[21.4] Taking screenshot..."
            )

            page.screenshot(
                path=screenshot,
                full_page=True
            )

            screenshots.append(
                screenshot
            )

            print(
                f"✅ Screenshot saved : "
                f"{screenshot}"
            )

            # ----------------------------------------
            # Browser result
            # ----------------------------------------

            if (
                title.strip() != ""
                and
                body_visible
            ):

                print(
                    f"✅ {browser_name} "
                    f"Browser Compatible"
                )

                passed += 1

            else:

                print(
                    f"❌ {browser_name} "
                    f"Browser Validation Failed"
                )

                failed += 1

                issues.append(
                    f"{browser_name} : "
                    "Page did not render correctly."
                )

        except Exception as e:

            print(
                f"❌ {browser_name} FAILED"
            )

            print(
                f"Error : {e}"
            )

            failed += 1

            issues.append(
                f"{browser_name} : {str(e)}"
            )

        finally:

            # ----------------------------------------
            # Close browser
            # ----------------------------------------

            if browser is not None:

                try:

                    browser.close()

                    print(
                        f"Browser closed : "
                        f"{browser_name}"
                    )

                except Exception as e:

                    print(
                        f"⚠️ Browser close error : "
                        f"{e}"
                    )

    # ------------------------------------------------
    # 21.5 CALCULATE SCORE
    # ------------------------------------------------

    print(
        "\n[21.5] Calculating browser results..."
    )

    total_browsers = len(
        browsers
    )

    if total_browsers > 0:

        score = int(
            (
                passed /
                total_browsers
            ) * 100
        )

    else:

        score = 0

    if failed == 0:

        status = "PASS"

        recommendations = [
            "Website rendered successfully "
            "in all tested browsers."
        ]

        issue = ""

        possible_reason = ""

        developer_action = ""

    else:

        status = "FAIL"

        recommendations = [
            "Fix browser-specific "
            "compatibility issues."
        ]

        issue = (
            f"{failed} browser(s) "
            "failed compatibility testing."
        )

        possible_reason = (
            "Browser-specific rendering, "
            "JavaScript or CSS differences."
        )

        developer_action = (
            "Review browser-specific "
            "CSS and JavaScript."
        )

    # ------------------------------------------------
    # 21.6 PRINT RESULT
    # ------------------------------------------------

    print("\n================================")
    print(
        f"Browsers Tested : "
        f"{total_browsers}"
    )

    print(
        f"Passed Browsers : "
        f"{passed}"
    )

    print(
        f"Failed Browsers : "
        f"{failed}"
    )

    print(
        f"Browser Score : "
        f"{score}%"
    )

    print(
        f"Status : {status}"
    )

    print("================================")

    if issues:

        print(
            "\nBrowser Issues:"
        )

        for issue_item in issues:

            print(
                f"❌ {issue_item}"
            )

    else:

        print(
            "\n✅ No browser compatibility "
            "issues detected."
        )

    print(
        "\n========== BROWSER COMPATIBILITY TEST END ==========\n"
    )

    # ------------------------------------------------
    # RETURN RESULT
    # ------------------------------------------------

    return {

        "module": "Browser Compatibility",

        "status": status,

        "browser_score": score,

        "browsers_tested": total_browsers,

        "passed_browsers": passed,

        "failed_browsers": failed,

        "issues": issues,

        "recommendations": recommendations,

        "screenshots": screenshots,

        "issue": issue,

        "possible_reason": possible_reason,

        "developer_action": developer_action

    }    
    
# ============================================================
# MODULE 22 : FINAL QA PDF REPORT GENERATION
# ============================================================
# ----------------------------------------------------
# MODULE 22 : FINAL REPORT GENERATION
# ----------------------------------------------------

def final_report_generation_test(results):

    print("\n========== FINAL REPORT GENERATION START ==========\n")

    try:

        # =================================================
        # 22.1 FUNCTIONAL MODULE COUNT
        # =================================================

        # Actual functional modules
        TOTAL_FUNCTIONAL_MODULES = 20

        # Module 22 itself is NOT included in results
        executed_modules = len(results)

        passed = sum(
            1
            for result in results
            if result.get("status", "").upper() == "PASS"
        )

        failed = sum(
            1
            for result in results
            if result.get("status", "").upper() == "FAIL"
        )

        not_available = sum(
            1
            for result in results
            if result.get("status", "").upper() == "NOT_AVAILABLE"
        )

        skipped = sum(
            1
            for result in results
            if result.get("status", "").upper() == "SKIPPED"
        )

        tested_modules = passed + failed

        if tested_modules > 0:

            functional_score = int(
                (passed / tested_modules) * 100
            )

        else:

            functional_score = 0

        # =================================================
        # 22.2 SUMMARY OBJECT
        # =================================================

        summary = {

            "total_functional_modules":
                TOTAL_FUNCTIONAL_MODULES,

            "executed_modules":
                executed_modules,

            "passed":
                passed,

            "failed":
                failed,

            "not_available":
                not_available,

            "skipped":
                skipped,

            "tested_modules":
                tested_modules,

            "functional_score":
                functional_score
        }

        # =================================================
        # 22.3 MODULE-WISE SUMMARY
        # NO INDIVIDUAL MODULE SCORE
        # =================================================

        module_summary = []

        for result in results:

            module_summary.append({

                "module":
                    result.get(
                        "module",
                        "Unknown Module"
                    ),

                "status":
                    result.get(
                        "status",
                        "UNKNOWN"
                    ),

                "issues":
                    result.get(
                        "issues",
                        []
                    ),

                "recommendations":
                    result.get(
                        "recommendations",
                        result.get(
                            "recommendation",
                            []
                        )
                    ),

                "possible_reason":
                    result.get(
                        "possible_reason",
                        ""
                    ),

                "developer_action":
                    result.get(
                        "developer_action",
                        ""
                    )
            })

        # =================================================
        # 22.4 FAILED MODULE DETAILS
        # =================================================

        failed_modules = []

        for result in results:

            if result.get("status", "").upper() != "FAIL":
                continue

            failed_modules.append({

                "module":
                    result.get(
                        "module",
                        "Unknown Module"
                    ),

                "issues":
                    result.get(
                        "issues",
                        []
                    ),

                "issue":
                    result.get(
                        "issue",
                        ""
                    ),

                "possible_reason":
                    result.get(
                        "possible_reason",
                        ""
                    ),

                "developer_action":
                    result.get(
                        "developer_action",
                        ""
                    )
            })

        # =================================================
        # 22.5 EXACT BROKEN LINKS
        # =================================================

        broken_links = []

        for result in results:

            module_name = result.get(
                "module",
                "Unknown Module"
            )

            possible_links = result.get(
                "broken_links",
                []
            )

            if not isinstance(
                possible_links,
                list
            ):
                continue

            for link in possible_links:

                if isinstance(link, dict):

                    broken_links.append({

                        "module":
                            module_name,

                        "url":
                            link.get(
                                "url",
                                ""
                            ),

                        "status":
                            link.get(
                                "status",
                                None
                            ),

                        "reason":
                            link.get(
                                "reason",
                                "Broken link"
                            )
                    })

        # Remove duplicates

        unique_broken_links = []

        seen_links = set()

        for link in broken_links:

            key = (
                link.get("module"),
                link.get("url"),
                link.get("status")
            )

            if key not in seen_links:

                seen_links.add(key)

                unique_broken_links.append(
                    link
                )

        broken_links = unique_broken_links

        # =================================================
        # 22.6 FAILED APIs
        # =================================================

        failed_apis = []

        for result in results:

            failures = result.get(
                "failed_requests",
                []
            )

            if not isinstance(
                failures,
                list
            ):
                continue

            for failure in failures:

                if isinstance(
                    failure,
                    dict
                ):

                    failed_apis.append({

                        "module":
                            result.get(
                                "module",
                                "API Validation"
                            ),

                        "method":
                            failure.get(
                                "method",
                                ""
                            ),

                        "url":
                            failure.get(
                                "url",
                                ""
                            ),

                        "status":
                            failure.get(
                                "status",
                                None
                            )
                    })

        # =================================================
        # 22.7 SECURITY ISSUES
        # =================================================

        security_issues = []

        for result in results:

            module_name = str(
                result.get(
                    "module",
                    ""
                )
            ).lower()

            if "security" in module_name:

                issues = result.get(
                    "issues",
                    []
                )

                if isinstance(
                    issues,
                    list
                ):

                    security_issues.extend(
                        issues
                    )

        # =================================================
        # 22.8 SEO ISSUES
        # =================================================

        seo_issues = []

        for result in results:

            module_name = str(
                result.get(
                    "module",
                    ""
                )
            ).lower()

            if "seo" not in module_name:
                continue

            issues = result.get(
                "issues",
                []
            )

            recommendations = result.get(
                "recommendations",
                []
            )

            if isinstance(
                issues,
                list
            ):

                seo_issues.extend(
                    issues
                )

            if isinstance(
                recommendations,
                list
            ):

                seo_issues.extend(
                    recommendations
                )

        # =================================================
        # 22.9 ACCESSIBILITY ISSUES
        # =================================================

        accessibility_issues = []

        for result in results:

            module_name = str(
                result.get(
                    "module",
                    ""
                )
            ).lower()

            if "accessibility" not in module_name:
                continue

            issues = result.get(
                "issues",
                []
            )

            if isinstance(
                issues,
                list
            ):

                accessibility_issues.extend(
                    issues
                )

        # =================================================
        # 22.10 ALL ISSUES
        # =================================================

        all_issues = []

        for result in results:

            issues = result.get(
                "issues",
                []
            )

            if not isinstance(
                issues,
                list
            ):
                continue

            for issue in issues:

                if issue:

                    all_issues.append({

                        "module":
                            result.get(
                                "module",
                                "Unknown Module"
                            ),

                        "issue":
                            issue
                    })

        # =================================================
        # 22.11 AI SUGGESTIONS
        # =================================================

        ai_suggestions = []

        if failed > 0:

            ai_suggestions.append(
                "Prioritize fixing failed functional modules."
            )

        if broken_links:

            ai_suggestions.append(
                "Review and correct the broken links listed in this report."
            )

        if failed_apis:

            ai_suggestions.append(
                "Investigate failed API endpoints and verify backend responses."
            )

        if security_issues:

            ai_suggestions.append(
                "Review security headers and apply the required security policies."
            )

        if seo_issues:

            ai_suggestions.append(
                "Improve SEO configuration including metadata, robots.txt, sitemap.xml and structured data where applicable."
            )

        if accessibility_issues:

            ai_suggestions.append(
                "Resolve accessibility issues and verify WCAG compliance."
            )

        if not ai_suggestions:

            ai_suggestions.append(
                "No major automated issues were detected. Perform manual exploratory testing."
            )

        # Remove duplicate suggestions

        ai_suggestions = list(
            dict.fromkeys(
                ai_suggestions
            )
        )

        # =================================================
        # 22.12 SCREENSHOTS
        # =================================================

        screenshots = []

        for result in results:

            # Single screenshot
            single = result.get(
                "screenshot"
            )

            if single:

                screenshots.append(
                    single
                )

            # Multiple screenshots
            multiple = result.get(
                "screenshots",
                []
            )

            if isinstance(
                multiple,
                list
            ):

                screenshots.extend(
                    item
                    for item in multiple
                    if item
                )

        screenshots = list(
            dict.fromkeys(
                screenshots
            )
        )

        # =================================================
        # 22.13 FINAL REPORT OBJECT
        # =================================================

        final_report = {

            "module":
                "Final Report Generation",

            "status":
                "PASS",

            "summary":
                summary,

            "module_summary":
                module_summary,

            "failed_modules":
                failed_modules,

            "broken_links":
                broken_links,

            "failed_apis":
                failed_apis,

            "security_issues":
                list(
                    dict.fromkeys(
                        security_issues
                    )
                ),

            "seo_issues":
                list(
                    dict.fromkeys(
                        seo_issues
                    )
                ),

            "accessibility_issues":
                list(
                    dict.fromkeys(
                        accessibility_issues
                    )
                ),

            "all_issues":
                all_issues,

            "ai_suggestions":
                ai_suggestions,

            "screenshots":
                screenshots
        }

        # =================================================
        # 22.14 PRINT SUMMARY
        # =================================================

        print("\n===========================================")
        print("FINAL QA REPORT")
        print("===========================================")

        print(
            f"Total Functional Modules : "
            f"{TOTAL_FUNCTIONAL_MODULES}"
        )

        print(
            f"Executed Modules         : "
            f"{executed_modules}"
        )

        print(
            f"Passed                   : "
            f"{passed}"
        )

        print(
            f"Failed                   : "
            f"{failed}"
        )

        print(
            f"Not Available            : "
            f"{not_available}"
        )

        print(
            f"Skipped                  : "
            f"{skipped}"
        )

        print(
            f"Tested Modules           : "
            f"{tested_modules}"
        )

        print(
            f"Functional Score         : "
            f"{functional_score}%"
        )

        print("-------------------------------------------")

        # =================================================
        # 22.15 BROKEN LINKS
        # =================================================

        print("\nBROKEN LINKS")

        if broken_links:

            for index, link in enumerate(
                broken_links,
                start=1
            ):

                print(
                    f"{index}. "
                    f"[{link['module']}] "
                    f"{link['url']} "
                    f"| Status: {link['status']} "
                    f"| {link['reason']}"
                )

        else:

            print(
                "No broken links detected."
            )

        # =================================================
        # 22.16 FAILED APIs
        # =================================================

        print("\nFAILED APIs")

        if failed_apis:

            for index, api in enumerate(
                failed_apis,
                start=1
            ):

                print(
                    f"{index}. "
                    f"{api['method']} "
                    f"{api['url']} "
                    f"| Status: {api['status']}"
                )

        else:

            print(
                "No failed APIs detected."
            )

        # =================================================
        # 22.17 AI SUGGESTIONS
        # =================================================

        print("\nAI SUGGESTIONS")

        for suggestion in ai_suggestions:

            print(
                f"• {suggestion}"
            )

        print("\n===========================================")
        print(
            "FINAL REPORT GENERATION COMPLETED"
        )
        print("===========================================\n")

        # =================================================
        # IMPORTANT
        # Do NOT append this report to results
        # =================================================

        return final_report

    except Exception as e:

        print(
            "\n❌ FINAL REPORT GENERATION ERROR"
        )

        print(
            f"Error : {e}"
        )

        return {

            "module":
                "Final Report Generation",

            "status":
                "FAIL",

            "summary": {

                "total_functional_modules":
                    20,

                "executed_modules":
                    len(results),

                "passed":
                    0,

                "failed":
                    1,

                "not_available":
                    0,

                "skipped":
                    0,

                "tested_modules":
                    1,

                "functional_score":
                    0
            },

            "issues": [
                str(e)
            ],

            "ai_suggestions": [
                "Review final report generation logic."
            ],

            "screenshots": []
        }
 
# =====================================
# Main Functional Testing
# =====================================

def functional_testing(url):

    results = []

    TOTAL_MODULES = 20

    print("\n===========================================")
    print("STARTING FUNCTIONAL TEST")
    print("===========================================\n")

    browser = None

    try:

        with sync_playwright() as p:

            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # FIX: sane page-level defaults so individual actions
            # (clicks, fills, waits) don't hang for the full 30s+
            page.set_default_timeout(DEFAULT_NAV_TIMEOUT)
            page.set_default_navigation_timeout(DEFAULT_NAV_TIMEOUT)

            # ====================================================
            # MODULE 1 : WEBSITE OPEN
            # ====================================================

            print("\nRunning Module 1 : Website Open")

            try:

                results.append(
                    website_open_test(page, url)
                )

            except Exception as e:

                print("❌ Module 1 : Website Open Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Website Opens",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 2 : NAVIGATION LINKS
            # ====================================================

            print("\nRunning Module 2 : Navigation Links")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(2000)

                results.append(
                    navigation_links_test(page, url)
                )

            except Exception as e:

                print("❌ Module 2 : Navigation Links Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Navigation Links",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 3 : NAVBAR
            # ====================================================

            print("\nRunning Module 3 : Navbar")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(1500)

                results.append(
                    navbar_test(page)
                )

            except Exception as e:

                print("❌ Module 3 : Navbar Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Navbar",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 4 : FOOTER
            # ====================================================

            print("\nRunning Module 4 : Footer")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(1500)

                results.append(
                    footer_test(page, url)
                )

            except Exception as e:

                print("❌ Module 4 : Footer Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Footer",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 5 : BUTTONS
            # ====================================================

            print("\nRunning Module 5 : Buttons")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(1500)

                results.append(
                    buttons_test(page)
                )

            except Exception as e:

                print("❌ Module 5 : Buttons Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Buttons",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 6 : FORMS VALIDATION
            # ====================================================

            print("\nRunning Module 6 : Forms Validation")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(1500)

                results.append(
                    form_validation_test(page)
                )

            except Exception as e:

                print("❌ Module 6 : Forms Validation Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Form Validation",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 7 : IMAGES
            # ====================================================

            print("\nRunning Module 7 : Images")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(1500)

                results.append(
                    image_test(page, url)
                )

            except Exception as e:

                print("❌ Module 7 : Images Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Images",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 8 : CONTENT VALIDATION
            # ====================================================

            print("\nRunning Module 8 : Content Validation")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(1500)

                results.append(
                    content_validation_test(page)
                )

            except Exception as e:

                print("❌ Module 8 : Content Validation Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Content Validation",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 9 : CONTENT QUALITY
            # ====================================================

            print("\nRunning Module 9 : Content Quality")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(3000)

                results.append(
                    content_quality_test(page)
                )

            except Exception as e:

                print("❌ Module 9 : Content Quality Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Content Quality",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 10 : AUTHENTICATION TESTING
            # ====================================================

            print("\nRunning Module 10 : Authentication Testing")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(3000)

                results.append(
                    authentication_test(page)
                )

            except Exception as e:

                print("❌ Module 10 : Authentication Testing Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Authentication Testing",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 11 : SESSION & COOKIES
            # ====================================================

            print("\nRunning Module 11 : Session & Cookies")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(3000)

                results.append(
                    session_cookie_test(page)
                )

            except Exception as e:

                print("❌ Module 11 : Session & Cookies Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Session & Cookies",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 12 : (Intentionally skipped - see search_functionality_test)
            # ====================================================

            # ====================================================
            # MODULE 13 : ACCESSIBILITY (WCAG)
            # ====================================================

            print("\nRunning Module 13 : Accessibility (WCAG)")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(3000)

                results.append(
                    accessibility_check(page)
                )

            except Exception as e:

                print("❌ Module 13 : Accessibility (WCAG) Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Accessibility (WCAG)",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 14 : SEO TESTING
            # ====================================================

            print("\nRunning Module 14 : SEO Testing")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(5000)

                results.append(
                    seo_test(page, url)
                )

            except Exception as e:

                print("❌ Module 14 SEO Error")
                print(f"Error : {e}")

                results.append({
                    "module": "SEO",
                    "status": "FAIL",
                    "seo_score": 0,
                    "issues": [str(e)],
                    "recommendations": [
                        "Review SEO test implementation."
                    ],
                    "screenshots": [],
                    "issue": str(e),
                    "possible_reason":
                        "SEO module execution failed.",
                    "developer_action":
                        "Fix SEO validation logic."
                })

            # ====================================================
            # MODULE 15 : RESPONSIVE DESIGN
            # ====================================================

            print("\nRunning Module 15 : Responsive Design")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(4000)

                results.append(
                    responsive_test(page)
                )

            except Exception as e:

                print("❌ Module 15 : Responsive Design Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Responsive Design",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 16 : SECURITY HEADERS
            # ====================================================

            print("\nRunning Module 16 : Security Headers")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(4000)

                results.append(
                    security_headers_test(page, url)
                )

            except Exception as e:

                print("❌ Module 16 : Security Headers Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Security Headers",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 17 : CONSOLE ERROR DETECTION
            # ====================================================

            print("\nRunning Module 17 : Console Error Detection")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(3000)

                results.append(
                    console_error_detection(page)
                )

            except Exception as e:

                print("❌ Module 17 : Console Error Detection Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Console Error Detection",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 18 : BROKEN RESOURCES
            # ====================================================

            print("\nRunning Module 18 : Broken Resources")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(3000)

                results.append(
                    broken_resources_test(page)
                )

            except Exception as e:

                print("❌ Module 18 : Broken Resources Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Broken Resources",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 19 : ERROR PAGE (404) HANDLING TESTING
            # ====================================================

            print("\nRunning Module 19 : Error Page (404) Handling")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(3000)

                results.append(
                    error_page_test(page)
                )

            except Exception as e:

                print("❌ Module 19 : Error Page (404) Handling Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "Error Page (404) Handling",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 20 : API VALIDATION
            # ====================================================

            print("\nRunning Module 20 : API Validation")

            try:

                safe_goto(page, url)
                page.wait_for_timeout(3000)

                results.append(
                    api_validation_test(page)
                )

            except Exception as e:

                print("❌ Module 20 : API Validation Error")
                print(f"Error : {e}")

                results.append(
                    {
                    "module": "API Validation",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "This module crashed unexpectedly during execution.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                }
                )

            # ====================================================
            # MODULE 21 : BROWSER COMPATIBILITY
            # ====================================================

            print("\nRunning Module 21 : Browser Compatibility")

            try:

                results.append(
                    browser_compatibility_test(p, url)
                )

            except Exception as e:

                print("❌ Module 21 Browser Compatibility Error")
                print(f"Error : {e}")

                results.append({
                    "module": "Browser Compatibility",
                    "status": "FAIL",
                    "issue": str(e),
                    "issues": [str(e)],
                    "possible_reason": "Browser compatibility module crashed unexpectedly.",
                    "recommendation": "Review module logs and retry.",
                    "recommendations": ["Review module logs and retry."],
                    "developer_action": "Check Playwright execution logs for this module.",
                    "screenshot": "",
                    "screenshots": []
                })

            # ====================================================
            # MODULE 22 : FINAL REPORT GENERATION
            # ====================================================

            print("\nRunning Module 22 : Final Report Generation")

            try:
                final_report = final_report_generation_test(results)
            except Exception as e:
                print(f"❌ Module 22 Final Report Error : {e}")
                final_report = None

            # ====================================================
            # CLOSE BROWSER
            # ====================================================

            try:
                browser.close()
            except Exception:
                pass

        # ========================================================
        # FINAL SUMMARY
        # ========================================================

        executed_modules = len(results)

        passed = sum(1 for result in results if result.get("status") == "PASS")
        failed = sum(1 for result in results if result.get("status") == "FAIL")
        not_available = sum(1 for result in results if result.get("status") == "NOT_AVAILABLE")
        skipped = sum(1 for result in results if result.get("status") == "SKIPPED")
        partial = sum(1 for result in results if result.get("status") == "PARTIAL")

        tested_modules = passed + failed

        if tested_modules > 0:
            score = int((passed / tested_modules) * 100)
        else:
            score = 0

        # ========================================================
        # FINAL PRINT
        # ========================================================

        print("\n===========================================")
        print("FUNCTIONAL TEST COMPLETED")
        print("===========================================")
        print(f"Total Modules     : {TOTAL_MODULES}")
        print(f"Executed Modules  : {executed_modules}")
        print(f"Passed            : {passed}")
        print(f"Failed            : {failed}")
        print(f"Not Available     : {not_available}")
        print(f"Skipped           : {skipped}")
        print(f"Partial           : {partial}")
        print(f"Tested Modules    : {tested_modules}")
        print(f"Score             : {score}%")
        print("-------------------------------------------")

        if executed_modules == TOTAL_MODULES:
            print(f"✅ All {TOTAL_MODULES} modules executed.")
        else:
            remaining = TOTAL_MODULES - executed_modules
            print(f"⚠️ {executed_modules} of {TOTAL_MODULES} modules executed.")
            print(f"⏳ {remaining} module(s) pending.")

        print("===========================================\n")

        # ========================================================
        # RETURN FINAL RESULT
        # ========================================================

        return {
            "functional_score": score,
            "passed": passed,
            "failed": failed,
            "not_available": not_available,
            "skipped": skipped,
            "partial": partial,
            "tested_modules": tested_modules,
            "executed_modules": executed_modules,
            "total_modules": TOTAL_MODULES,
            "results": results
        }

    except Exception as e:

        # NOTE: with every module now wrapped in its own try/except above,
        # this outer except should only trigger for truly catastrophic
        # failures (e.g. browser could not launch at all, or Playwright
        # itself crashed) - not for a single slow page or timeout anymore.

        print("\n❌ Critical Functional Testing Error")
        print(f"Error : {e}")

        try:
            if browser is not None:
                browser.close()
        except Exception:
            pass

        executed_modules = len(results)

        passed = sum(1 for result in results if result.get("status") == "PASS")
        failed = sum(1 for result in results if result.get("status") == "FAIL")
        not_available = sum(1 for result in results if result.get("status") == "NOT_AVAILABLE")
        skipped = sum(1 for result in results if result.get("status") == "SKIPPED")
        partial = sum(1 for result in results if result.get("status") == "PARTIAL")

        tested_modules = passed + failed

        if tested_modules > 0:
            score = int((passed / tested_modules) * 100)
        else:
            score = 0

        return {
            "functional_score": score,
            "passed": passed,
            "failed": failed,
            "not_available": not_available,
            "skipped": skipped,
            "partial": partial,
            "tested_modules": tested_modules,
            "executed_modules": executed_modules,
            "total_modules": TOTAL_MODULES,
            "results": results,
            "issues": [str(e)],
            "recommendations": [
                "Verify the failed module.",
                "Review Playwright execution logs."
            ]
        }