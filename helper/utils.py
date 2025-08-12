# utils.py
from IPython.display import Image, display

def show_graph(graph, xray=False, as_mermaid=False, print_mermaid=False):
    """
    Visualize a LangGraph as an image or output Mermaid syntax for docs.

    Args:
        graph: The LangGraph object (compiled or not).
        xray (bool): Show internal details if supported.
        as_mermaid (bool): If True, return the Mermaid string.
        print_mermaid (bool): If True, print the Mermaid string to stdout.

    Returns:
        If as_mermaid: returns the Mermaid string.
        Otherwise: displays the image (in Jupyter/IPython).
    """
    g = graph.get_graph(xray=xray) if hasattr(graph, "get_graph") else graph
    if as_mermaid or print_mermaid:
        mermaid_str = g.draw_mermaid()
        if print_mermaid:
            print(mermaid_str)
        if as_mermaid:
            return mermaid_str
    else:
        try:
            display(Image(g.draw_mermaid_png()))
        except Exception as e:
            print(f"Could not display graph image. Error: {e}")
            print("Falling back to Mermaid syntax:")
            print(g.draw_mermaid())
