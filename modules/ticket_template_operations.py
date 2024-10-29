import re  # For regular expression matching

## DOCU for jira MD lang: https://jira.atlassian.com/secure/WikiRendererHelpAction.jspa?section=all

# Function to convert Jira markup to HTML
def jira_markup_to_html(text):
    # Convert headings
    for i in range(6, 0, -1):
        text = re.sub(rf'h{i}\.\s*(.*)', rf'<h{i}>\1</h{i}>', text)

    # Convert bold (**text** or *text*)
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<strong>\1</strong>', text)

    # Convert italics (_text_)
    text = re.sub(r'_(.*?)_', r'<em>\1</em>', text)

    # Convert underlines (+text+)
    text = re.sub(r'\+(.*?)\+', r'<u>\1</u>', text)

    # Convert strikethrough (-text-)
    text = re.sub(r'-(.*?)-', r'<del>\1</del>', text)

    # Convert monospace ({{text}})
    text = re.sub(r'{{(.*?)}}', r'<code>\1</code>', text)

    # Convert citations (??text??)
    text = re.sub(r'\?\?(.*?)\?\?', r'<cite>\1</cite>', text)

    # Convert superscript (^text^)
    text = re.sub(r'\^(.*?)\^', r'<sup>\1</sup>', text)

    # Convert subscript (~text~)
    text = re.sub(r'~(.*?)~', r'<sub>\1</sub>', text)

    # Convert inserted text (++text++)
    text = re.sub(r'\+\+(.*?)\+\+', r'<ins>\1</ins>', text)

    # Convert code blocks
    text = re.sub(r'\{code\}(.*?)\{code\}', r'<pre><code>\1</code></pre>', text, flags=re.DOTALL)

    # Convert blockquotes {quote}
    text = re.sub(r'\{quote\}(.*?)\{quote\}', r'<blockquote>\1</blockquote>', text, flags=re.DOTALL)

    # Convert horizontal rules (----)
    text = re.sub(r'----', r'<hr/>', text)

    # Convert links [text|url]
    text = re.sub(r'\[(.*?)\|(.*?)\]', r'<a href="\2">\1</a>', text)

    # Convert images !image_url!
    text = re.sub(r'!(.*?)!', r'<img src="\1" alt="Image"/>', text)

    # Convert unordered lists
    lines = text.split('\n')
    in_list = False
    new_lines = []
    for line in lines:
        if re.match(r'^\* ', line):
            if not in_list:
                new_lines.append('<ul>')
                in_list = True
            new_lines.append('<li>' + line[2:] + '</li>')
        else:
            if in_list:
                new_lines.append('</ul>')
                in_list = False
            new_lines.append(line)
    if in_list:
        new_lines.append('</ul>')
    text = '\n'.join(new_lines)

    # Convert ordered lists
    lines = text.split('\n')
    in_list = False
    new_lines = []
    for line in lines:
        if re.match(r'^# ', line):
            if not in_list:
                new_lines.append('<ol>')
                in_list = True
            new_lines.append('<li>' + line[2:] + '</li>')
        else:
            if in_list:
                new_lines.append('</ol>')
                in_list = False
            new_lines.append(line)
    if in_list:
        new_lines.append('</ol>')
    text = '\n'.join(new_lines)

    # Convert tables
    lines = text.split('\n')
    in_table = False
    new_lines = []
    for line in lines:
        if re.match(r'^\|\|', line):
            if not in_table:
                new_lines.append('<table>')
                in_table = True
            # Header row
            cells = re.findall(r'\|\|(.*?)\|\|', line)
            row = '<tr>' + ''.join(f'<th>{cell.strip()}</th>' for cell in cells) + '</tr>'
            new_lines.append(row)
        elif re.match(r'^\|', line):
            if not in_table:
                new_lines.append('<table>')
                in_table = True
            # Data row
            cells = re.findall(r'\|(.*?)\|', line)
            row = '<tr>' + ''.join(f'<td>{cell.strip()}</td>' for cell in cells) + '</tr>'
            new_lines.append(row)
        else:
            if in_table:
                new_lines.append('</table>')
                in_table = False
            new_lines.append(line)
    if in_table:
        new_lines.append('</table>')
    text = '\n'.join(new_lines)

    # Convert line breaks
    text = text.replace('\n', '<br/>')

    return text

def find_placeholders(text):
    #return re.findall(r"\{\{(.*?)\}\}", text)
    return re.findall(r"\{\$(.*?)\$\}", text)