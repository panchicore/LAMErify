```
# LAMErify:
```

```
## requirements:
```

osx:
brew install lame

linux:
apt-get install lame

pip install -r deploy/requirements.txt

```
## run:
```
first time: cp local_settings.py.sample local_settings.py
first time: edit local_settings.py
always: python api.py

```
## to-do:
```

1. make async task for the hard work
2. web hook to callback the results