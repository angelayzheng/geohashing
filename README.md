# Geohashing

Geohashing is an algorithm originating from [xkcd](https://xkcd.com/) comic #426:

![xkcd comic for geohashing](https://imgs.xkcd.com/comics/geohashing.png)

It has now turned into a [worldwide daily game](https://geohashing.site/geohashing/Main_Page) with a variety of accompanying coordinate calculators, such as [geohashing.info](https://geohashing.info/).

This repository contains two Python scripts:

- `geohash_calc.py` calculates the closest daily coordinates to a given location, based on the geohashing algorithm
- `send_email.py` sends the calculation results in an email to a configured email address

These scripts can be scheduled to run daily, as I have configured for myself, so that I can be notified when the daily coordinates in one of my surrounding graticules are close-ish to my location. Maybe one day I will manage to get there.

## Credits

I converted the algorithms used by [geohashing.info](https://geohashing.info/) (which are open source [here](https://github.com/Eupeodes/gh) by [Marten Tacoma](https://github.com/Eupeodes)) from PHP to Python with the help of LLMs.

## Setup

These steps are for Windows — sorry to anyone using other operating systems.

1. Clone this repo:

```bash
git clone https://github.com/angelayzheng/geohashing.git
cd geohashing
```

2. Install dependencies (of which there is only one at the moment):

```bash
pip install -r requirements.txt
```

3. Configure the settings in the `config` folder:

- **`geohash_config.json`**: Set your home coordinates (`home_lat`, `home_lon`) and adjust other parameters as needed (decimal precision, distance threshold, etc.)
- **`email_config.json`**: Set your SMTP server details, sender email, password, and recipient email (for Gmail, use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password)

4. Test that everything works (because it probably won't work first try):

```bash
python scripts/send_email.py
```

5. (Optional) Set it up to run on a schedule:

- This requires a bit of finagling. I used Windows Task Scheduler and it was fairly simple — [this tutorial](https://www.geeksforgeeks.org/python/schedule-python-script-using-windows-scheduler/) probably works.

6. Have fun if you decide to adventure out one day!
