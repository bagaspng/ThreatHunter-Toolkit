"""Deep diagnostic: understand exactly how turnstile is set up on erpskrip.id/kontak"""
from DrissionPage import ChromiumPage, ChromiumOptions
import time
import json

CHROME_ARGUMENTS = [
    "-no-first-run", "-force-color-profile=srgb",
    "-metrics-recording-only", "-password-store=basic",
    "-no-default-browser-check", "-disable-background-mode",
    "-deny-permission-prompts",
    "-accept-lang=en-US", "--disable-usage-stats",
    "--disable-crash-reporter", "--no-sandbox",
]

options = ChromiumOptions()
for arg in CHROME_ARGUMENTS:
    options.set_argument(arg)

driver = ChromiumPage(addr_or_opts=options)
driver.get("https://erpskrip.id/kontak")
print("Page loading... waiting 8 seconds")
time.sleep(8)

print(f"=== PAGE TITLE: {driver.title} ===\n")

# 1. Full Turnstile analysis
diag = driver.run_js("""
    var r = {};

    // All elements with data-sitekey
    r.sitekey_els = Array.from(document.querySelectorAll('[data-sitekey]')).map(e => ({
        tag: e.tagName,
        id: e.id,
        class: e.className,
        sitekey: e.getAttribute('data-sitekey'),
        rendered: e.querySelector('iframe') !== null,
        html: e.outerHTML.substring(0, 400)
    }));

    // All cf-turnstile divs
    r.cf_divs = Array.from(document.querySelectorAll('.cf-turnstile')).map(e => ({
        id: e.id,
        sitekey: e.getAttribute('data-sitekey'),
        html: e.outerHTML.substring(0, 400)
    }));

    // All turnstile-related inputs
    r.inputs = Array.from(document.querySelectorAll('input')).filter(e =>
        e.name.includes('turnstile') || e.name.includes('cf-') || e.id.includes('turnstile')
    ).map(e => ({
        name: e.name, id: e.id, type: e.type,
        value: (e.value || '').substring(0, 60),
        form_id: e.form ? e.form.id : 'none'
    }));

    // All iframes
    r.iframes = Array.from(document.querySelectorAll('iframe')).map(f => ({
        src: f.src.substring(0, 200),
        width: f.width, height: f.height,
        style: f.style.cssText.substring(0, 100)
    }));

    // All forms
    r.forms = Array.from(document.querySelectorAll('form')).map(f => ({
        id: f.id, action: f.action.substring(0, 100),
        method: f.method,
        inputs: Array.from(f.querySelectorAll('input,textarea')).map(i => i.name).join(', ')
    }));

    // Turnstile API
    r.turnstile_api = typeof window.turnstile !== 'undefined';
    if (r.turnstile_api) {
        r.turnstile_methods = Object.keys(window.turnstile);
        try { r.api_response = turnstile.getResponse() || 'EMPTY'; }
        catch(e) { r.api_response = 'error: ' + e.message; }
    }

    // CF scripts
    r.cf_scripts = Array.from(document.querySelectorAll('script')).filter(s =>
        s.src && (s.src.includes('cloudflare') || s.src.includes('turnstile'))
    ).map(s => s.src);

    // Check onloadTurnstileCallback
    r.onload_callback = typeof window.onloadTurnstileCallback;

    // Check if there's a div with id containing 'turnstile' or 'cf'
    r.turnstile_ids = Array.from(document.querySelectorAll('[id*="turnstile"],[id*="cf-"]')).map(e => ({
        tag: e.tagName, id: e.id, class: e.className
    }));

    // Check for shadow roots on potential containers
    r.shadow_roots = [];
    document.querySelectorAll('div').forEach(function(d) {
        if (d.shadowRoot) {
            r.shadow_roots.push({id: d.id, class: d.className.substring(0, 50)});
        }
    });

    return JSON.stringify(r, null, 2);
""")

print(diag)

# 2. Look at the full page HTML around the form/turnstile area
print("\n\n=== SEARCHING FOR TURNSTILE IN PAGE SOURCE ===")
html_snippet = driver.run_js("""
    var html = document.documentElement.outerHTML;
    var idx = html.indexOf('turnstile');
    if (idx === -1) return 'NOT FOUND in HTML';

    // Get all occurrences
    var results = [];
    var searchStart = 0;
    while (true) {
        idx = html.indexOf('turnstile', searchStart);
        if (idx === -1) break;
        var start = Math.max(0, idx - 100);
        var end = Math.min(html.length, idx + 200);
        results.push('...context[' + idx + ']: ' + html.substring(start, end).replace(/\\n/g, ' '));
        searchStart = idx + 1;
        if (results.length > 15) break;
    }
    return results.join('\\n---\\n');
""")
print(html_snippet)

# 3. Check console errors
print("\n\n=== PERFORMANCE ENTRIES (CF-related) ===")
perf = driver.run_js("""
    var entries = performance.getEntriesByType('resource').filter(e =>
        e.name.includes('cloudflare') || e.name.includes('turnstile')
    ).map(e => ({name: e.name.substring(0, 150), status: e.responseStatus, duration: Math.round(e.duration)}));
    return JSON.stringify(entries, null, 2);
""")
print(perf)

driver.close()
print("\n=== DONE ===")
