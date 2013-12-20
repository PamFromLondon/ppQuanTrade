{
    "network": {
        "frontport": "tcp://127.0.0.1:5555",
        "backport": "tcp://127.0.0.1:5570",
        "logger": "tcp://127.0.0.1:5540"
    },
    "vocal": {
        "lang": "en",
        "encoding": "utf-8"
    },
    "truefx": {
        "user": "user",
        "password": "secret"
    },
    "mysql": {
        "hostname": "localhost",
        "user": "user",
        "password": "chut",
        "database": "dbname",
        "data_start": "2000-01-03"
    },
    "twitter": {
        "user": "",
        "password": ""
    },
    "sources": {
        "rbloggers": "feedburner.com/RBloggers",
        "quantopian": "https://www.quantopian.com/feed",
        "unix": "http://www.unixgarden.com/index.php/feed",
        "reuters": "http://feeds.reuters.com/reuters/financialsNews",
        "news": "http://economie.trader-finance.fr/rss.php",
        "example": "http://cyber.law.harvard.edu/rss/examples/rss2sample.xml"
    },
    "quandl": {
        "apikey": ""
    },
    "notifymyandroid": {
        "url_notify": "http://www.notifymyandroid.com/publicapi/notify",
        "url_check": "http://www.notifymyandroid.com/publicapi/verify",
        "apikey": ""
    },
    "grid": {
        "controller": ["192.168.0.12"],
        "nodes": ["192.168.0.17", "192.168.0.20"],
        "name": "xavier",
        "password": "",
        "port": 5555
    }
}
