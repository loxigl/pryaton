#!/bin/bash
watchmedo auto-restart \
  --directory=./src --directory=./main.py \
  --pattern="*.py" --recursive \
  -- python main.py
