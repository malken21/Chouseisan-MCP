
from playwright.async_api import async_playwright
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ChouseisanError(Exception):
    pass

class NetworkError(ChouseisanError):
    pass

class ScrapingError(ChouseisanError):
    pass

class ChouseisanClient:
    BASE_URL = "https://chouseisan.com"

    def __init__(self):
        pass

    async def create_event(self, title: str, memo: str = "", dates: str = "") -> str:
        logger.info(f"Creating event: {title}")
        print("DEBUG: entering create_event")
        async with async_playwright() as p:
            print("DEBUG: launched playwright")
            browser = await p.chromium.launch(headless=True)
            print("DEBUG: launched browser")
            page = await browser.new_page()
            try:
                await page.goto(self.BASE_URL)
                print("DEBUG: navigated to base url")
                
                await page.fill('input[name="name"]', title)
                await page.fill('textarea[name="comment"]', memo)
                await page.fill('textarea[name="kouho"]', dates)
                print("DEBUG: filled form")
                
                # Click create button
                # Use specific selector
                # Try multiple selectors effectively
                btn = (await page.locator('#createBtn, #create_event_submit_btn, button:has-text("出欠表をつくる")').all())[0]
                if await btn.count() > 0 or True: # .all() returns elements, not locator with count in async? No, locator.all() returns list of locators.
                    # Wait, let's use first variable
                    btn_locator = page.locator('#createBtn, #create_event_submit_btn, button:has-text("出欠表をつくる")').first
                    if await btn_locator.count() > 0:
                        print(f"DEBUG: clicking button {await btn_locator.inner_text()}")
                        await btn_locator.click()
                    else:
                        raise ChouseisanError("Submit button not found")
                
                print("DEBUG: clicked submit")
                
                # Wait for confirmation page/URL
                try:
                    # New event URL input - wait explicitly
                    # class="new-event-url-input"
                    print("DEBUG: waiting for url input")
                    await page.wait_for_selector('input.new-event-url-input', timeout=10000)
                    url = await page.input_value('input.new-event-url-input')
                    print(f"DEBUG: found url {url}")
                except Exception as e:
                    print(f"DEBUG: wait failed {e}, trying fallback")
                    # Fallback if redirection happens directly
                    # Check if we are on a page that looks like event page
                    if "s?h=" in page.url:
                         url = page.url
                    else:
                         # try waiting for url change
                         await page.wait_for_url("**/s?h=*", timeout=5000)
                         url = page.url

                logger.info(f"Event created successfully: {url}")
                return url
            except Exception as e:
                logger.exception("Error creating event")
                print(f"DEBUG: exception {e}")
                raise ChouseisanError(f"Error creating event: {e}")
            finally:
                print("DEBUG: closing browser")
                await browser.close()


    async def get_event_info(self, event_url: str) -> Dict[str, Any]:
        logger.info(f"Fetching event info from: {event_url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(event_url)
                
                # Title
                print("DEBUG: getting title")
                title = await page.locator('h1').inner_text()
                print(f"DEBUG: title {title}")
                
                # Dates
                dates = []
                
                # Try #nittei table first (Vertical layout often used in Chouseisan)
                # Selector found: #nittei tr td:first-child
                # Often the first row is header "日程", so we might skip it?
                # The subagent said "The very first element matched by this selector is the column header '日程'".
                print("DEBUG: getting dates locator")
                # Try #nittei table first
                # Selector found: #nittei tr td:first-child
                nittei_locator = page.locator('#nittei tr td:first-child')
                print("DEBUG: counting nittei")
                nittei_count = await nittei_locator.count()
                print(f"DEBUG: nittei count {nittei_count}")
                if nittei_count > 0:
                    for i in range(nittei_count):
                        td = nittei_locator.nth(i)
                        text = await td.inner_text()
                        if text.strip() == "日程": # Skip header
                            continue
                        dates.append(text)
                
                # If no dates found, try the old selector (header of attendance table)
                if not dates:
                    # Try table headers
                    th_locator = page.locator('#attendance-table th.valign-middle')
                    th_count = await th_locator.count()
                    if th_count > 2:
                        for i in range(2, th_count):
                             th = th_locator.nth(i)
                             dates.append(await th.inner_text())
                
                logger.info(f"Found {len(dates)} dates")
                return {
                    "title": title,
                    "dates": dates,
                    "url": event_url
                }
            except Exception as e:
                logger.exception("Error getting event info")
                raise ChouseisanError(f"Error getting event info: {e}")
            finally:
                await browser.close()

    async def add_response(self, event_url: str, name: str, comment: str = "", availability: Optional[List[int]] = None) -> bool:
        if availability is None:
            availability = []
            
        logger.info(f"Adding response for {name} to: {event_url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(event_url)
                
                # Click "出欠を入力する"
                # Selector found in analysis: #add_btn
                await page.click('#add_btn')
                
                # Wait for form
                # Check for name input "f_name" (id) or name="name"
                await page.wait_for_selector('input[name="name"]', timeout=5000)
                
                # Fill name
                await page.fill('input[name="name"]', name)
                
                # Fill comment (hitokoto)
                # Selector from dump: input[name="hitokoto"]
                if await page.locator('input[name="hitokoto"]').count() > 0:
                    await page.fill('input[name="hitokoto"]', comment)
                else:
                    logger.warning("Comment field 'hitokoto' not found, skipping.")
                
                # Fill availability by clicking buttons
                # User Input Values: 2 (O), 1 (Tri), 0 (X)
                # Button classes: .oax-0 (O), .oax-1 (Tri), .oax-2 (X)
                button_class_map = {2: "oax-0", 1: "oax-1", 0: "oax-2"}
                
                # Click buttons for each date
                for i, status in enumerate(availability):
                    field_name = f"kouho{i+1}"
                    # Check if hidden input exists
                    if await page.locator(f'input[name="{field_name}"]').count() > 0:
                        button_class = button_class_map.get(status, "oax-2") # Default to X if unknown
                        # Find the parent element of the hidden input
                        # Then find the button with the appropriate class within that parent
                        # Use JavaScript to click the button relative to the hidden input
                        await page.evaluate(f'''() => {{
                            const hiddenInput = document.querySelector('input[name="{field_name}"]');
                            if (hiddenInput) {{
                                const parent = hiddenInput.parentElement;
                                const button = parent.querySelector('.{button_class}');
                                if (button) {{
                                    button.click();
                                }}
                            }}
                        }}''')
                        # Small delay to ensure the click is processed
                        await page.wait_for_timeout(100)
                    else:
                        logger.warning(f"Availability field {field_name} not found.")

                # Submit
                # Button id="memUpdBtn" name="add"
                await page.click('#memUpdBtn')
                
                # Wait for completion
                await page.wait_for_load_state("domcontentloaded")
                
                return True
            except Exception as e:
                logger.exception("Error adding response")
                raise ChouseisanError(f"Error adding response: {e}")
            finally:
                await browser.close()
