# pages/dataset1/page.py
import dash
from components.dataset_page import build_dataset_page

dash.register_page(__name__, path="/dataset1", title="dataset1 // coldparse")


def layout():
    return build_dataset_page("datasets/dataset1.toml")
