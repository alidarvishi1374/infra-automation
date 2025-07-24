#!/bin/bash

# install python3.12-env
sudo apt install python3.12-venv

# create a virtual environment
python3 -m venv ~/.venv

# source virtuall env
source ~/.venv/bin/activate

# install requirements packages
pip install streamlit streamlit-tags pyyaml

# run code
streamlit run app.py
