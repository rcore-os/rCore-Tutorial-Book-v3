# See #91.
# Solution: if selector div.section cannot be found in a page, changing the pattern from div:section to
# div > section can be a reasonable idea after observation.
import os
html_list = []
def collect_html(path):
    for item in os.listdir(path):
        new_path = path + '/' + item
        if os.path.isdir(new_path):
            collect_html(new_path)
        else:
            _, ext = os.path.splitext(new_path)
            if ext == '.html':
                html_list.append(new_path)

collect_html('build/html')
for html_file in html_list:
    html_content = ""
    with open(html_file, 'r') as f:
        html_content_lines = f.readlines()
        for line in html_content_lines:
            html_content += line
    if html_content.find('<div class="section') == -1:
        html_content = html_content.replace('div.section', 'div > section')
        with open(html_file, 'w') as f:
            f.write(html_content)
