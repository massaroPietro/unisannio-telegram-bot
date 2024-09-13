from typing import List
import requests
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.error import BadRequest
import os
import asyncio
import logging
from models import get_session, Department, Alert
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

bot = Bot(token=os.getenv('TELEGRAM_TOKEN'))

BASE_URL = os.getenv('BASE_URL')
ALERT_CLASSES_IDENTIFIER = os.getenv("ALERT_CLASSES_IDENTIFIER")
INTERVAL_SECONDS = int(os.getenv('INTERVAL_SECONDS'))
MESSAGE_DELAY = int(os.getenv('MESSAGE_DELAY'))
RETRY_ATTEMPTS = int(os.getenv('RETRY_ATTEMPTS'))

session = get_session()


def scrape_alerts(department: Department):
    try:
        response = requests.get(department.url + "/avvisi-didattica")

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            alerts = soup.find_all('div', class_='mini-card')
            results = []

            for alert in alerts:
                link = alert.find('a')['href']
                full_link = f"{BASE_URL}{link}"

                if not session.query(Alert).filter_by(link=full_link).all():
                    results.append(Alert(
                        department_name=department.name,
                        link=full_link,
                    ))

            if results:
                session.add_all(results)
                session.commit()

            logging.info(f"Scraped {len(results)} alerts for {department.name}")
        else:
            logging.error(f"Failed to retrieve alerts for {department.name}: Status code {response.status_code}")

    except Exception as e:
        session.rollback()
        logging.error(f"Error scraping alerts for {department.name}: {str(e)}")


def scrape_alert_details(url: str):
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        title_span = soup.find('h1').find('span')
        title = title_span.get_text(strip=True) if title_span else None

        details_div = soup.find('div', class_=ALERT_CLASSES_IDENTIFIER)
        content = details_div.get_text(separator="\n", strip=True) if details_div else None

        if content is None and title is None:
            return None

        message = ""

        if title:
            message += f"📌 *{title}*\n\n"
        else:
            title = "Titolo non disponibile"
            message += f"📌 *{title}*\n\n"

        if content:
            message += f"{content}"
        else:
            message += f"🔗 [Leggi di più]({url})"

        return title, content, message
    else:
        logging.error("Failed to retrieve details for %s: Status code %d", url, response.status_code)
        return None


async def send_telegram_messages(alerts: List[Alert]):
    for alert in alerts:
        title, content, message = scrape_alert_details(alert.link)

        retry_attempts = RETRY_ATTEMPTS
        for attempt in range(retry_attempts):
            try:
                alert.sent_at = datetime.now()
                alert.status = 'sent'

                session.add(alert)

                await bot.send_message(chat_id=alert.department.channel_id, text=message, parse_mode='Markdown')
                logging.info(f"Message sent successfully for {alert.department_name}")

                session.commit()
                break
            except BadRequest as e:
                logging.error("BadRequest error: %s (%s). Link: %s", e, type(e).__name__, alert.link)
                alternative_message = f"📌 *{title}*\n\n🔗 [Leggi di più]({alert.link})"
                try:
                    await bot.send_message(chat_id=alert.department.channel_id, text=alternative_message,
                                     parse_mode='Markdown')
                    logging.info("Alternative message sent successfully for %s", alert.department_name)

                    session.commit()
                    break
                except Exception as inner_e:
                    logging.error("Failed to send alternative message: %s (%s). Link: %s", inner_e,
                                  type(inner_e).__name__, alert.link)
                    session.rollback()
                break
            except Exception as e:
                logging.error("Attempt %d failed: %s (%s). Link: %s", attempt + 1, e, type(e).__name__, alert.link)
                if attempt < retry_attempts - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    logging.error("Failed to send message after several attempts for %s.", alert.department_name)
                    session.rollback()


async def main():
    while True:
        departments = session.query(Department).all()

        if not departments:
            logging.info(f"No departments found")
            break

        for department in departments:
            logging.info(f"Checking for new alerts for {department.name}...")
            scrape_alerts(department)

            alerts_to_sent = session.query(Alert).filter_by(department_name=department.name, status='pending').all()

            if alerts_to_sent:
                await send_telegram_messages(alerts_to_sent)
            else:
                logging.info(f"No new alerts to send for {department.name}")

        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.info("Starting the Unisannio alert scraper")
    asyncio.run(main())
