import base64
import fitbit
from datetime import date
from datetime import datetime
from dateutil.relativedelta import relativedelta

import pandas as pd
import numpy as np

import yaml
import requests
import logging

logger = logging.getLogger(__name__)

class FitbitHelper(object):
    def __init__(self):
        with open('app_config.yaml') as fp:
            self.app_config = yaml.load(fp)

        self.user_auth = None

        try:
            with open('user_auth.yaml') as fp:
                self.user_auth = yaml.load(fp)
        except IOError:
            logging.info("Error reading user_auth.yaml. It may need to be created using the update_authorization_codes method")

        if self.user_auth is not None:
            self.__init_client()

    def __init_client(self):
        self.authd_client = fitbit.Fitbit(
            self.app_config['client_id'],
            self.app_config['client_secret'],
            access_token = self.user_auth['access_token'],
            refresh_token = self.user_auth['refresh_token']
        )

    def get_authorization_url(self):
        """
            The URL returned by this method is used to authorize the application to access the users FitBit data.

            Follow the returned URL in the browser.
            Authorize the application if required.
            Copy the code from the redirect url.
            Example: https://maccas.net/fitbit?code=7b64c4b088b9c841d15bcac15d4aa7433d35af3e#_=_
            The code you need to copy from that example is 7b64c4b088b9c841d15bcac15d4aa7433d35af3e. Don't include the "#_=_".

            This code can be passed to the update_authorization_codes method to update the user_auth.yaml file with auth tokens.
        """
        params = {
            'response_type': 'code',
            'client_id': self.app_config['client_id'],
            'redirect_uri': self.app_config['callback_url'],
            'scope': 'activity heartrate location nutrition profile settings sleep social weight',
            'expires_in': '604800',
                                    }
        return 'https://www.fitbit.com/oauth2/authorize?' + requests.compat.urlencode(params)

    def update_authorization_codes(self, user_code):
        """
        """
        auth_code = base64.b64encode(
            '{client_id}:{client_secret}'.format(
                client_id = self.app_config['client_id'],
                client_secret = self.app_config['client_secret']
            )
        )

        headers = {
            'Authorization': 'Basic {0}'.format(auth_code),
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = {
            "clientId": self.app_config['client_id'],
            "grant_type": "authorization_code",
            "redirect_uri": "https://maccas.net/fitbit",
            "code": user_code,
        }

        r = requests.post('https://api.fitbit.com/oauth2/token', headers = headers, data = data)

        with open('user_auth.yaml', 'w') as fp:
            yaml.dump(r.json(), fp)

        with open('user_auth.yaml', 'r') as fp:
            self.user_auth = yaml.load(fp)

        self.__init_client()

    def get_heart_rate_series(self, start_date = None, end_date = None):
        if start_date is None:
            start_date = date.today()

        if end_date is None:
            end_date = date.today()

        logger.debug("Heart rate series start_date: %s", start_date)
        logger.debug("Heart rate series end_date: %s", end_date)

        times, values = [], []
        for dt in pd.date_range(start_date, end_date, freq = 'D'):
            hr = self.authd_client.intraday_time_series('activities/heart', base_date = dt)

        for row in hr['activities-heart-intraday']['dataset']:
            h, m, s = [int(x) for x in row['time'].split(':')]

            times.append(datetime(dt.year,dt.month,dt.day,h,m,s))
            values.append(row['value'])

        return pd.Series(values, times).asfreq('1T')

    def get_sleep_series(self, dt = None):
        times, values = [], []
        for s in self.authd_client.sleep(dt)['sleep']:
            cur_date = datetime.strptime(s['dateOfSleep'], "%Y-%m-%d")
            for row in s['minuteData'][::-1]:
                h, m, s = [int(x) for x in row['dateTime'].split(':')]
                s = 0
                new_datetime = datetime(cur_date.year,cur_date.month,cur_date.day,h,m,s)
                times.append(new_datetime)
                values.append(int(row['value']))

                if h == 0 and m == 0:
                    cur_date = cur_date - relativedelta(days = 1)

        return pd.Series(values[::-1], times[::-1])
