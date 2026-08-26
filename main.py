from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from ingestion.webhook_listener import router as webhook_router
from ingestion.mcp_proxy import router as mcp_proxy_router

app = FastAPI(title="EqlipZ Pay API", docs_url=None)

app.mount("/dashboard", StaticFiles(directory="static", html=True), name="static")

app.include_router(webhook_router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(mcp_proxy_router, prefix="/mcp", tags=["MCP Proxy"])

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html(req: Request):
    html_content = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
    ).body.decode("utf-8")
    
    custom_css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600&display=swap');
        
        body {
            background-color: #f4f4f4 !important;
        }
        
        .swagger-ui, .swagger-ui *, .swagger-ui button, .swagger-ui input, .swagger-ui select {
            font-family: 'Outfit', sans-serif !important;
        }
        
        .swagger-ui .opblock, 
        .swagger-ui .models,
        .swagger-ui .model-container,
        .swagger-ui .parameters-col_description input,
        .swagger-ui .btn,
        .swagger-ui .dialog-ux .modal-ux,
        .swagger-ui .dialog-ux .modal-ux-header,
        .swagger-ui pre,
        .swagger-ui code,
        .swagger-ui .highlight-code,
        .swagger-ui .model-box,
        .swagger-ui .model {
            border-radius: 0px !important;
        }

        .swagger-ui .opblock {
            border: none !important;
            background-image: 
                repeating-linear-gradient(0deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px),
                repeating-linear-gradient(90deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px),
                repeating-linear-gradient(180deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px),
                repeating-linear-gradient(270deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px) !important;
            background-size: 1px 100%, 100% 1px, 1px 100%, 100% 1px !important;
            background-position: 0 0, 0 0, 100% 0, 0 100% !important;
            background-repeat: no-repeat !important;
            box-shadow: none !important;
            background-color: #ffffff !important;
            margin-bottom: 24px !important;
        }
        
        .swagger-ui .models {
            border: none !important;
            background-image: 
                repeating-linear-gradient(0deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px),
                repeating-linear-gradient(90deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px),
                repeating-linear-gradient(180deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px),
                repeating-linear-gradient(270deg, #c0c0c0, #c0c0c0 6px, transparent 6px, transparent 12px) !important;
            background-size: 1px 100%, 100% 1px, 1px 100%, 100% 1px !important;
            background-position: 0 0, 0 0, 100% 0, 0 100% !important;
            background-repeat: no-repeat !important;
            box-shadow: none !important;
            background-color: #ffffff !important;
        }
        
        .swagger-ui .opblock .opblock-summary {
            border-bottom: 1px dashed #c0c0c0 !important;
            padding: 8px 16px !important; /* Tighter premium padding */
        }
        
        .swagger-ui .opblock .opblock-summary-method {
            padding: 4px 10px !important;
            font-size: 12px !important;
            min-width: 60px !important;
        }
        
        .swagger-ui .opblock .opblock-summary-path {
            font-size: 14px !important;
        }
        
        .swagger-ui section.models .model-container {
            background-color: transparent !important;
            padding: 12px 16px !important;
        }
        
        .swagger-ui section.models h4 {
            padding: 12px 16px !important;
            font-size: 14px !important;
            border-bottom: 1px dashed #c0c0c0 !important;
        }
        
        .swagger-ui section.models .model-container:hover,
        .swagger-ui .model-box:hover,
        .swagger-ui .model:hover {
            background-color: transparent !important;
            background: transparent !important;
        }
        
        .swagger-ui .model-box {
            border-radius: 0px !important;
        }

        .swagger-ui .info {
            margin: 24px 0 !important;
        }

        .swagger-ui .info .title {
            font-size: 28px !important;
            font-weight: 500 !important;
            letter-spacing: -0.5px !important;
            display: flex !important;
            align-items: flex-end !important;
            gap: 12px !important;
            flex-wrap: wrap !important;
        }
        
        .swagger-ui .info .title span {
            display: flex !important;
            align-items: flex-end !important;
            gap: 8px !important;
            margin: 0 0 4px 0 !important;
        }
        
        .swagger-ui .info .title pre, 
        .swagger-ui .info .title .version-stamp, 
        .swagger-ui .info .title .version,
        .swagger-ui pre.version,
        .swagger-ui .version-stamp {
            border-radius: 0px !important;
            margin: 0 !important;
            transform: none !important;
            vertical-align: bottom !important;
        }

        /* Enforce custom blue and complete black */
        .swagger-ui .opblock-summary-method {
            border-radius: 0 !important;
        }
        
        .swagger-ui .btn {
            border: 1px dashed #4348E8 !important;
            color: #4348E8 !important;
            box-shadow: none !important;
        }
        
        .swagger-ui .btn.execute {
            background-color: #4348E8 !important;
            color: #ffffff !important;
        }
        
        /* Hide scrollbar */
        * {
            -ms-overflow-style: none !important;
            scrollbar-width: none !important;
        }
        *::-webkit-scrollbar {
            display: none !important;
        }
        
        /* Full width and Light Fonts Enforcements */
        .swagger-ui .wrapper {
            max-width: 100% !important;
            padding: 0 48px !important;
        }
        
        .swagger-ui, .swagger-ui *, .swagger-ui p, .swagger-ui span, .swagger-ui div {
            font-weight: 300 !important;
        }
        
        .swagger-ui b, .swagger-ui strong, .swagger-ui h1, .swagger-ui h2, .swagger-ui h3, .swagger-ui h4, .swagger-ui h5, .swagger-ui .info .title {
            font-weight: 400 !important;
        }
        
        .swagger-ui .opblock .opblock-summary-method, .swagger-ui .btn {
            font-weight: 500 !important;
        }
        
        /* Custom Selectors */
        .swagger-ui select {
            -webkit-appearance: none !important;
            -moz-appearance: none !important;
            appearance: none !important;
            border-radius: 0px !important;
            border: 1px dashed #c0c0c0 !important;
            background-color: transparent !important;
            padding: 4px 24px 4px 8px !important;
            background-image: url("data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%23444444%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-5.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22%2F%3E%3C%2Fsvg%3E") !important;
            background-repeat: no-repeat !important;
            background-position: right 8px center !important;
            background-size: 8px auto !important;
            box-shadow: none !important;
            outline: none !important;
        }
        
        .swagger-ui select:focus {
            border: 1px dashed #4348E8 !important;
            outline: none !important;
            box-shadow: none !important;
        }
        
        .swagger-ui select option {
            background-color: #ffffff !important;
            color: #000000 !important;
            border-radius: 0px !important;
            padding: 8px !important;
        }
        
        /* Copy to clipboard icon cleanup */
        .swagger-ui .copy-to-clipboard {
            background: transparent !important;
            border: none !important;
            border-radius: 0px !important;
            padding: 4px !important;
        }
        
        .swagger-ui .copy-to-clipboard svg {
            fill: #444444 !important;
        }
        
        /* Parameter Table Layout Fixes */
        .swagger-ui table.parameters {
            width: 100% !important;
            display: table !important;
        }
        
        .swagger-ui .parameters-col_name {
            width: 300px !important; /* Prevent text wrapping */
            vertical-align: top !important;
        }
        
        .swagger-ui .parameters-col_description {
            width: auto !important;
            vertical-align: top !important;
        }
        
        .swagger-ui .parameters-col_description input[type="text"] {
            width: 100% !important;
            max-width: 100% !important;
            border: 1px dashed #c0c0c0 !important;
            background: transparent !important;
        }
        
        .swagger-ui .parameters-col_description input[type="text"]:focus {
            border: 1px dashed #4348E8 !important;
            outline: none !important;
        }
        /* Custom JS Dropdown Styles */
        .custom-select-wrapper {
            position: relative;
            width: 100%;
            min-width: 160px;
            font-family: 'Outfit', sans-serif !important;
            font-weight: 300 !important;
        }
        
        .custom-select-display {
            background-color: transparent !important;
            border: 1px dashed #c0c0c0;
            padding: 6px 10px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 14px;
            color: #000000;
        }
        
        .custom-select-display.active {
            border-color: #4348E8;
        }
        
        .custom-select-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            width: 100%;
            background: #ffffff;
            border: 1px dashed #4348E8;
            border-top: none;
            z-index: 9999;
            max-height: 200px;
            overflow-y: auto;
        }
        
        .custom-select-dropdown.show {
            display: block;
        }
        
        .custom-select-item {
            padding: 8px 10px;
            cursor: pointer;
            font-size: 14px;
            color: #000000;
            background: #ffffff;
            border-bottom: 1px dashed #e0e0e0;
        }
        
        .custom-select-item:last-child {
            border-bottom: none;
        }
        
        .custom-select-item:hover {
            background: #f4f4f4;
            color: #4348E8;
        }
        
        /* Ensure dropdowns aren't clipped by containers */
        .swagger-ui .opblock-body, .swagger-ui .responses-wrapper, .swagger-ui .responses-inner {
            overflow: visible !important;
        }
    </style>
    """
    
    custom_js = """
    <script>
    document.addEventListener("DOMContentLoaded", () => {
        function setNativeValue(element, value) {
            const valueSetter = Object.getOwnPropertyDescriptor(element, 'value').set;
            const prototype = Object.getPrototypeOf(element);
            const prototypeValueSetter = Object.getOwnPropertyDescriptor(prototype, 'value').set;
            if (valueSetter && valueSetter !== prototypeValueSetter) {
                prototypeValueSetter.call(element, value);
            } else {
                valueSetter.call(element, value);
            }
            element.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function customizeSelects() {
            document.querySelectorAll('.swagger-ui select:not(.customized)').forEach(select => {
                select.classList.add('customized');
                select.style.display = 'none';

                const wrapper = document.createElement('div');
                wrapper.className = 'custom-select-wrapper';
                select.parentNode.insertBefore(wrapper, select);
                wrapper.appendChild(select);

                const display = document.createElement('div');
                display.className = 'custom-select-display';
                display.innerHTML = `<span>${select.options[select.selectedIndex]?.text || ''}</span> <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square" stroke-linejoin="miter"><polyline points="6 9 12 15 18 9"></polyline></svg>`;
                wrapper.appendChild(display);

                const dropdown = document.createElement('div');
                dropdown.className = 'custom-select-dropdown';
                
                Array.from(select.options).forEach(option => {
                    const item = document.createElement('div');
                    item.className = 'custom-select-item';
                    item.textContent = option.text;
                    item.addEventListener('click', (e) => {
                        e.stopPropagation();
                        display.querySelector('span').textContent = option.text;
                        setNativeValue(select, option.value);
                        dropdown.classList.remove('show');
                        display.classList.remove('active');
                    });
                    dropdown.appendChild(item);
                });
                wrapper.appendChild(dropdown);

                display.addEventListener('click', (e) => {
                    e.stopPropagation();
                    document.querySelectorAll('.custom-select-dropdown.show').forEach(d => {
                        if (d !== dropdown) {
                            d.classList.remove('show');
                            d.previousElementSibling.classList.remove('active');
                        }
                    });
                    dropdown.classList.toggle('show');
                    display.classList.toggle('active');
                });
                
                select.addEventListener('change', () => {
                   display.querySelector('span').textContent = select.options[select.selectedIndex]?.text || '';
                });
            });
        }

        document.addEventListener('click', () => {
            document.querySelectorAll('.custom-select-dropdown.show').forEach(d => {
                d.classList.remove('show');
                d.previousElementSibling.classList.remove('active');
            });
        });

        const observer = new MutationObserver(() => { customizeSelects(); });
        observer.observe(document.body, { childList: true, subtree: true });
    });
    </script>
    """
    
    html_content = html_content.replace("</head>", f"{custom_css}{custom_js}</head>")
    return HTMLResponse(html_content)

@app.get("/")
def read_root():
    return {"status": "operational", "service": "EqlipZ Pay"}

