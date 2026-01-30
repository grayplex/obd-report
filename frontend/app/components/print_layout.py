PRINT_CSS = """
@media print {
    .no-print,
    .no-print * {
        display: none !important;
    }

    /* Preserve dark theme colors when printing */
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
    color-adjust: exact !important;

    * {
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
        color-adjust: exact !important;
    }

    body {
        background: #222 !important;
        background-color: #222 !important;
        color: #fff !important;
    }

    html {
        background: #222 !important;
        background-color: #222 !important;
    }

    .container-fluid {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
        background: #222 !important;
    }

    h1, h2, h3, h4, h5, h6, p, span, div {
        color: #fff !important;
    }

    .card {
        background: #303030 !important;
        border: 1px solid #444 !important;
        break-inside: avoid;
        page-break-inside: avoid;
    }

    .card-body {
        background: #303030 !important;
    }

    .text-muted {
        color: #aaa !important;
    }

    .chart-section {
        break-inside: avoid;
        page-break-inside: avoid;
        margin-bottom: 10px;
    }

    .section-break {
        break-before: page;
        page-break-before: always;
    }

    .js-plotly-plot {
        break-inside: avoid;
        page-break-inside: avoid;
    }

    .modebar-container {
        display: none !important;
    }

    h3, h4 {
        break-after: avoid;
        page-break-after: avoid;
    }

    @page {
        size: letter landscape;
        margin: 0.25in;
    }
}
"""


def get_print_css():
    """Return the print CSS string to be included in app's index_string or assets."""
    return PRINT_CSS
