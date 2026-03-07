from services.crawler.parser import extract_clean_text


def test_extract_clean_text_removes_ui_and_keeps_content() -> None:
    raw_html = """
    <html>
      <body>
        <div id="side-bar">Sidebar links</div>
        <div id="page-content">
          <h1>SCP-173</h1>
          <div class="rate-box-with-credit-button">Rate widget</div>
          <p>Recovered near Kyoto in 1993.</p>
          <div class="collapsible-block">
            <p>Experiment log entry mentions Prague.</p>
          </div>
        </div>
      </body>
    </html>
    """

    clean_text = extract_clean_text(raw_html)

    assert "Sidebar links" not in clean_text
    assert "Rate widget" not in clean_text
    assert "Recovered near Kyoto in 1993." in clean_text
    assert "Experiment log entry mentions Prague." in clean_text
