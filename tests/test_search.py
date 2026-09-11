from linagent.tools.web.browser import _clean_html_to_markdown

def test_html_cleaning():
    sample_html = """
    <html>
      <head><style>body { color: red; }</style></head>
      <body>
        <nav><a href="/home">Home</a></nav>
        <h1>Welcome to Linux</h1>
        <p>This is an <b>awesome</b> automated system.</p>
        <script>alert("test");</script>
        <ul>
          <li>Kernel 6.12</li>
          <li>Systemd</li>
        </ul>
        <footer>Copyright 2026</footer>
      </body>
    </html>
    """
    cleaned = _clean_html_to_markdown(sample_html)
    assert "alert" not in cleaned
    assert "color: red" not in cleaned
    assert "Welcome to Linux" in cleaned
    assert "awesome" in cleaned
    assert "Kernel 6.12" in cleaned
