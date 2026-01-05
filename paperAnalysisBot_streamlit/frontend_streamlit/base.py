# frontend_streamlit/base.py
import streamlit as st

class BaseTab:
    def __init__(self, title: str):
        self.title = title

    def render(self):
        raise NotImplementedError("Subclasses must implement render()")