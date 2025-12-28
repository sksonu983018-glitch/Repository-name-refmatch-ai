from flask import Flask, render_template, request, jsonify
import re
from typing import List, Dict, Set
import html

app = Flask(__name__)

class BibEntry:
    def __init__(self, id: str, surname: str, year: str):
        self.id = id
        self.surname = surname
        self.year = year

def format_article(article_html: str, reference_text: str) -> str:
    # Parse references
    bib = []
    stop_words = {'journal', 'science', 'nature', 'review', 'reports', 
                 'et', 'al', 'the', 'and', 'for', 'with', 'from', 
                 'vol', 'issue', 'page', 'pp'}
    
    for line in reference_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        id_match = re.match(r'^(\d+)\.?', line)
        year_match = re.search(r'\b((?:18|19|20)\d{2})\b', line)
        
        if id_match and year_match:
            year_str = year_match.group(1)
            year_idx = line.find(year_str)
            author_segment = line[:year_idx].strip()
            author_segment = re.sub(r'^\d+\.?\s+', '', author_segment)
            
            name_match = re.search(r'[A-ZÀ-ÖØ-Þ][a-zA-ZÀ-ÖØ-Þà-öø-ÿ-]+', author_segment)
            if name_match:
                surname = name_match.group(0).lower()
                if surname not in stop_words:
                    bib.append(BibEntry(id_match.group(1), surname, year_str))
    
    # Process article - preserve all HTML formatting
    working_html = article_html
    
    year_regex = re.compile(r'\b((?:18|19|20)\d{2})[a-z]?\b', re.IGNORECASE)
    matches = []
    
    for year_match in year_regex.finditer(working_html):
        found_base_year = year_match.group(1).lower()
        year_end_pos = year_match.end()
        
        context_start = max(0, year_match.start() - 70)
        raw_context = working_html[context_start:year_match.start()]
        clean_context = re.sub(r'<[^>]+>', ' ', raw_context).lower()
        
        candidates = [entry for entry in bib if entry.year == found_base_year]
        best_candidate = None
        min_distance = 999
        
        for entry in candidates:
            surname_regex = re.compile(rf'\b{re.escape(entry.surname)}\b')
            for m in surname_regex.finditer(clean_context):
                distance = len(clean_context) - m.start()
                if distance < min_distance:
                    min_distance = distance
                    best_candidate = entry
        
        if best_candidate:
            matches.append((year_end_pos, best_candidate.id))
    
    # Group matches
    matches.sort(reverse=True, key=lambda x: x[0])
    grouped = []
    
    for pos, id in matches:
        found = False
        for group in grouped:
            if abs(group[0] - pos) < 35:
                group[1].add(id)
                found = True
                break
        if not found:
            grouped.append((pos, {id}))
    
    # Insert superscripts
    result = working_html
    for pos, ids in grouped:
        sorted_ids = sorted([int(id) for id in ids])
        tag = f'<sup>[{", ".join(str(id) for id in sorted_ids)}]</sup>'
        
        insert_pos = pos
        following = result[pos:pos+5]
        
        if following.strip().startswith(')'):
            closing_idx = result.find(')', pos)
            if closing_idx != -1 and closing_idx - pos < 10:
                insert_pos = closing_idx + 1
        
        result = result[:insert_pos] + tag + result[insert_pos:]
    
    # Minimal formatting - preserve all original styling
    # Only add italics to specific terms if not already formatted
    terms = [r'et al\.?', r'in vivo', r'in vitro', r'p\s*[<>=]\s*\d*\.?\d+']
    for term in terms:
        # Only italicize if not already inside HTML tags
        pattern = rf'(?<![<>/])(\b{term}\b)(?![<>/])'
        def add_italic(match):
            text = match.group(1)
            # Check if already inside a tag
            if '<' in text or '>' in text:
                return text
            return f'<i>{text}</i>'
        result = re.sub(pattern, add_italic, result, flags=re.IGNORECASE)
    
    # Clean up adjacent superscripts
    result = re.sub(r'</sup>\s*,?\s*<sup>', ', ', result)
    
    def deduplicate_superscripts(match):
        content = match.group(1)
        ids = [int(n) for n in re.findall(r'\d+', content) if n.isdigit()]
        unique_ids = sorted(set(ids))
        return f'<sup>[{", ".join(str(id) for id in unique_ids)}]</sup>'
    
    result = re.sub(r'<sup>\[([^\]]+)\]</sup>', deduplicate_superscripts, result)
    result = re.sub(r'([^.,\s\(\)\[])<sup>', r'\1 <sup>', result)
    
    return result

# HTML Template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>RefMatch AI - Rich Text Format</title>
    <meta charset="UTF-8">
    <style>
        * { box-sizing: border-box; }
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background-color: #4f46e5; color: white; padding: 20px; text-align: center; border-radius: 10px; margin-bottom: 30px; }
        .main { display: flex; gap: 20px; margin-bottom: 30px; }
        .panel { flex: 1; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        
        .editor-box {
            width: 100%;
            min-height: 400px;
            max-height: 600px;
            padding: 15px;
            border: 2px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
            overflow-y: auto;
            background-color: #ffffff;
            line-height: 1.6;
        }
        
        .editor-box:focus {
            outline: none;
            border-color: #4f46e5;
        }
        
        .editor-box:empty:before {
            content: attr(data-placeholder);
            color: #999;
        }
        
        .output { 
            width: 100%; 
            min-height: 400px; 
            max-height: 600px;
            padding: 15px; 
            border: 2px solid #4CAF50; 
            border-radius: 5px; 
            background-color: #ffffff; 
            overflow-y: auto;
            line-height: 1.6;
        }
        
        .controls { text-align: center; margin: 20px 0; }
        button { padding: 12px 30px; margin: 0 10px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; transition: all 0.3s; }
        button:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        .format-btn { background-color: #4f46e5; color: white; }
        .reset-btn { background-color: #6c757d; color: white; }
        .example-btn { background-color: #20c997; color: white; }
        .copy-btn { background-color: #198754; color: white; }
        .loading { display: none; text-align: center; color: #4f46e5; font-size: 18px; margin: 20px 0; }
        
        .info-box {
            background-color: #e3f2fd;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
        }
        
        .info-box h4 { margin: 0 0 10px 0; color: #1976D2; }
        .info-box p { margin: 5px 0; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 RefMatch AI - Rich Text Formatter</h1>
            <p>Preserve original formatting while adding citations automatically!</p>
        </div>
        
        <div class="info-box">
            <h4>📋 How to Use:</h4>
            <p>1️⃣ Copy your formatted article from Word/Google Docs (with all colors, fonts, bold, italic)</p>
            <p>2️⃣ Paste it in the Article Content box (formatting will be preserved!)</p>
            <p>3️⃣ Add your numbered references in the Reference List box</p>
            <p>4️⃣ Click "Format Article" - Citations will be added automatically! 🚀</p>
        </div>
        
        <div class="main">
            <div class="panel">
                <h3>📝 Article Content (Rich Text)</h3>
                <div id="article" class="editor-box" contenteditable="true" data-placeholder="Paste your formatted article here... (Bold, Italic, Colors will be preserved!)"></div>
            </div>
            
            <div class="panel">
                <h3>📚 Reference List</h3>
                <div id="references" class="editor-box" contenteditable="true" data-placeholder="Paste numbered references here:
1. Smith, J. 2020...
2. Johnson, A. 2019..."></div>
            </div>
        </div>
        
        <div class="controls">
            <button class="example-btn" onclick="loadExample()">📄 Load Example</button>
            <button class="reset-btn" onclick="resetAll()">🔄 Reset</button>
            <button class="format-btn" onclick="formatArticle()">✨ Format Article</button>
        </div>
        
        <div id="loading" class="loading">
            <h3>⏳ Processing... Please wait</h3>
        </div>
        
        <div class="panel" id="outputPanel" style="display: none;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3>✅ Formatted Article (With Citations)</h3>
                <button class="copy-btn" onclick="copyOutput()">📋 Copy HTML</button>
            </div>
            <div id="output" class="output"></div>
        </div>
    </div>
    
    <script>
        const exampleArticle = `<h1 style="color: #2c3e50; font-family: Georgia;">Emerging concerns of microplastic deposition in marine life: A review</h1>
<p style="color: #34495e;"><strong>Shreya R. Patil</strong><br><em>Assistant Professor in Zoology</em><br>Veer Wajekar A.S.C. College, Phunde, Navi Mumbai-400702</p>
<h2 style="color: #e74c3c;">Abstract</h2>
<p style="text-align: justify;">Microplastic contamination has emerged as a <strong>pervasive and persistent</strong> form of marine pollution, attracting increasing scientific attention due to its widespread occurrence and potential biological impacts.</p>
<h2 style="color: #3498db;">Keywords</h2>
<p><em>Microplastics, Marine pollution, Bioaccumulation, Marine organisms</em></p>
<h2 style="color: #16a085;">1. Environmental Occurrence and Distribution</h2>
<p style="text-align: justify;">Recent investigations have demonstrated that microplastics are present in deep-sea sediments, polar regions, and remote oceanic gyres (Cózar et al., 2014; Van Cauwenberghe et al., 2013).</p>
<h2 style="color: #16a085;">2. Uptake and Tissue Distribution</h2>
<p style="text-align: justify;"><strong>Filter-feeding organisms</strong> are particularly susceptible (Cole et al., 2013). Fibrous particles increase inflammation (Wright et al., 2013).</p>
<h2 style="color: #16a085;">3. Chemical Contaminants</h2>
<p style="text-align: justify;">This leads to <span style="color: #c0392b;"><strong>synergistic toxic effects</strong></span> (Rochman et al., 2013).</p>`;
        
        const exampleRefs = `1. Cózar A, Echevarría F, González-Gordillo JI, et al. Plastic debris in the open ocean. Proc Natl Acad Sci USA. 2014;111(28):10239-10244.
2. Van Cauwenberghe L, Vanreusel A, Mees J, Janssen CR. Microplastic pollution in deep-sea sediments. Environ Pollut. 2013;182:495-499.
3. Cole M, Lindeque P, Fileman E, et al. Microplastic ingestion by zooplankton. Environ Sci Technol. 2013;47(12):6646-6655.
4. Wright SL, Thompson RC, Galloway TS. The physical impacts of microplastics on marine organisms: A review. Environ Pollut. 2013;178:483-492.
5. Rochman CM, Hoh E, Kurobe T, Teh SJ. Ingested plastic transfers hazardous chemicals to fish and induces hepatic stress. Sci Rep. 2013;3:3263.`;
        
        function loadExample() {
            document.getElementById('article').innerHTML = exampleArticle;
            document.getElementById('references').innerText = exampleRefs;
        }
        
        function resetAll() {
            document.getElementById('article').innerHTML = '';
            document.getElementById('references').innerHTML = '';
            document.getElementById('outputPanel').style.display = 'none';
            document.getElementById('output').innerHTML = '';
        }
        
        async function formatArticle() {
            const articleDiv = document.getElementById('article');
            const referencesDiv = document.getElementById('references');
            
            const article = articleDiv.innerHTML;
            const references = referencesDiv.innerText;
            
            if (!article.trim() || !references.trim()) {
                alert('⚠️ Please provide both the article content and the reference list.');
                return;
            }
            
            document.getElementById('loading').style.display = 'block';
            
            try {
                const response = await fetch('/format', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        article: article,
                        references: references
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('output').innerHTML = data.formatted;
                    document.getElementById('outputPanel').style.display = 'block';
                    document.getElementById('outputPanel').scrollIntoView({ behavior: 'smooth' });
                } else {
                    alert('❌ Error: ' + data.error);
                }
            } catch (error) {
                alert('❌ Network error: ' + error);
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }
        
        function copyOutput() {
            const output = document.getElementById('output').innerHTML;
            navigator.clipboard.writeText(output).then(() => {
                alert('✅ HTML copied to clipboard!');
            });
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return HTML_TEMPLATE

@app.route('/format', methods=['POST'])
def format():
    try:
        data = request.json
        article = data.get('article', '')
        references = data.get('references', '')
        
        if not article or not references:
            return jsonify({'success': False, 'error': 'Missing input'})
        
        formatted = format_article(article, references)
        return jsonify({'success': True, 'formatted': formatted})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)