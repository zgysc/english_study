"""
英语口语练习工具 - Flask后端
功能：汉译英填空练习，支持多级别难度，3次错误后显示答案
"""

import json
import os
import random
import re
import urllib.parse
import requests as http_requests
from flask import Flask, render_template, request, jsonify, session, send_file, Response

app = Flask(__name__)
app.secret_key = 'english-practice-secret-key-2024'


def load_questions():
    """加载题库数据"""
    with open('data/questions.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def tokenize_english(sentence):
    """
    将英文句子拆分为单词token列表
    每个token是一个单词（可能含末尾标点）
    例如: "Hello, world!" -> ["Hello,", "world!"]
    空格由前端flex布局自动处理
    """
    tokens = re.findall(r"[a-zA-Z'']+[.,!?;:'\"]*", sentence)
    return tokens


def get_word_count(sentence):
    """统计英文句子中的单词数量"""
    words = re.findall(r"[a-zA-Z']+", sentence)
    return len(words)


@app.route('/')
def index():
    """首页 - 选择难度级别"""
    return render_template('index.html')


@app.route('/quiz')
def quiz():
    """练习页面"""
    level = request.args.get('level', 'cet6')
    if level not in ['cet6', 'ielts', 'toefl']:
        level = 'cet6'

    level_names = {
        'cet6': '英语六级',
        'ielts': '雅思',
        'toefl': '托福'
    }

    return render_template('quiz.html', level=level, level_name=level_names[level])


@app.route('/api/question', methods=['GET'])
def get_question():
    """获取一道随机题目"""
    level = request.args.get('level', 'cet6')
    if level not in ['cet6', 'ielts', 'toefl']:
        level = 'cet6'

    questions = load_questions()
    question_pool = questions.get(level, [])
    if not question_pool:
        return jsonify({'error': '该级别暂无题目'}), 404

    # 随机选择一道题
    idx = random.randint(0, len(question_pool) - 1)
    q = question_pool[idx]
    english = q['english']
    tokens = tokenize_english(english)
    word_count = get_word_count(english)

    # 构建单词token列表（每个token都是单词，可能含末尾标点）
    word_tokens = []
    for i, token in enumerate(tokens):
        # 提取纯单词部分（去除标点）作为答案
        pure_word = re.sub(r"[.,!?;:'\"]+$", '', token)
        word_tokens.append({
            'index': i,
            'display': token,
            'answer': pure_word
        })

    return jsonify({
        'chinese': q['chinese'],
        'english': english,
        'tokens': word_tokens,
        'word_count': word_count,
        'audio_id': f"{level}_{idx}"
    })


@app.route('/api/audio/<path:filename>')
def get_audio(filename):
    """提供本地预生成的语音文件"""
    audio_path = os.path.join('data', 'audio', filename)
    if os.path.exists(audio_path):
        return send_file(audio_path, mimetype='audio/mpeg')
    return jsonify({'error': '音频文件不存在'}), 404


@app.route('/api/speak')
def speak():
    """在线语音朗读（代理百度翻译TTS，国内可用，无需API密钥）"""
    text = request.args.get('text', '').strip()
    if not text:
        return jsonify({'error': '缺少文本参数'}), 400

    encoded_text = urllib.parse.quote(text)
    tts_url = f'https://fanyi.baidu.com/gettts?lan=en&text={encoded_text}&spd=2&source=web'

    try:
        resp = http_requests.get(tts_url, timeout=5,
                                  headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200 and len(resp.content) > 1000:
            return Response(
                resp.content,
                mimetype='audio/mpeg',
                headers={'Cache-Control': 'max-age=86400'}
            )
        else:
            return jsonify({'error': 'TTS服务暂时不可用'}), 502
    except Exception:
        return jsonify({'error': 'TTS服务连接失败'}), 502


@app.route('/api/check', methods=['POST'])
def check_answer():
    """检查用户答案"""
    data = request.get_json()
    user_answer = data.get('answer', '').strip()
    correct_answer = data.get('correct_answer', '').strip()
    attempt = data.get('attempt', 1)

    # 标准化比较：忽略大小写、多余空格、末尾标点差异
    def normalize(s):
        s = s.lower().strip()
        s = re.sub(r'\s+', ' ', s)
        s = s.rstrip('.,!?;:')
        return s

    is_correct = normalize(user_answer) == normalize(correct_answer)

    return jsonify({
        'is_correct': is_correct,
        'attempt': attempt,
        'show_answer': not is_correct and attempt >= 3,
        'correct_answer': correct_answer if (not is_correct and attempt >= 3) else None
    })


@app.route('/api/stats', methods=['POST'])
def update_stats():
    """更新练习统计（基于session）"""
    data = request.get_json()
    level = data.get('level', 'cet6')

    if 'stats' not in session:
        session['stats'] = {}

    if level not in session['stats']:
        session['stats'][level] = {'total': 0, 'correct': 0, 'wrong': 0}

    session['stats'][level]['total'] += 1
    if data.get('is_correct'):
        session['stats'][level]['correct'] += 1
    else:
        session['stats'][level]['wrong'] += 1

    session.modified = True

    return jsonify({'stats': session['stats'].get(level, {})})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
