import os
import sqlite3
import json
import re
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from tools import get_available_tools, get_tools_description

load_dotenv()

app = Flask(__name__)

# Use PORT environment variable for Render.com compatibility
PORT = int(os.environ.get('PORT', 5000))

# Initialize Gemini AI
api_key = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-pro')

# Load available tools
available_tools = {tool['name']: tool['function'] for tool in get_available_tools()}

def process_ai_request(user_message):
    """Process user request using AI and execute appropriate task management tools."""
    
    # Create a system prompt with available tools
    system_prompt = f"""You are a helpful AI assistant for task management. You have access to these tools:

{get_tools_description()}

When users ask you to perform actions, analyze their request and determine which tool to use. 

For common patterns:
- "show/list/get tasks" → use get_tasks
- "add/create task" → use add_task  
- "delete/remove task" → use delete_task
- "move/update task status" → use update_task_status
- "stats/statistics/summary" → use get_task_stats

User request: {user_message}"""

    try:
        # Generate response from Gemini to understand intent
        response = model.generate_content(system_prompt)
        ai_response = response.text
        
        # Enhanced pattern matching to detect and execute tool calls
        user_lower = user_message.lower()
        
        # Stats/Summary requests
        if any(word in user_lower for word in ["stats", "statistics", "summary", "progress", "overview"]):
            return available_tools['get_task_stats']()
        
        # Show/List tasks
        elif any(word in user_lower for word in ["show", "list", "get", "display"]) and "task" in user_lower:
            if "todo" in user_lower:
                return available_tools['get_tasks']("todo")
            elif any(word in user_lower for word in ["progress", "doing", "working"]):
                return available_tools['get_tasks']("in_progress")
            elif any(word in user_lower for word in ["done", "completed", "finished"]):
                return available_tools['get_tasks']("done")
            else:
                return available_tools['get_tasks']()
                
        # Add/Create task
        elif any(word in user_lower for word in ["add", "create", "new"]) and "task" in user_lower:
            # Enhanced parsing for task creation
            title, assignee, priority = parse_task_creation(user_message)
            return available_tools['add_task'](title, assignee=assignee, priority=priority)
            
        # Delete/Remove task
        elif any(word in user_lower for word in ["delete", "remove"]) and "task" in user_lower:
            task_id = extract_task_id(user_message)
            if task_id:
                return available_tools['delete_task'](task_id)
            return "Please specify a task ID to delete (e.g., 'delete task 5')"
            
        # Move/Update task status
        elif any(word in user_lower for word in ["move", "update", "change"]) and "task" in user_lower:
            task_id = extract_task_id(user_message)
            status = extract_status(user_message)
            if task_id and status:
                return available_tools['update_task_status'](task_id, status)
            return "Please specify task ID and status (e.g., 'move task 1 to done')"
        
        # Default: return AI response for general questions
        else:
            return ai_response
            
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"

def parse_task_creation(message):
    """Parse task creation message to extract title, assignee, and priority."""
    words = message.split()
    title = "New Task"
    assignee = ""
    priority = 5
    
    # Look for "for [name]" pattern
    for i, word in enumerate(words):
        if word.lower() == "for" and i + 1 < len(words):
            assignee = words[i + 1].strip(',.')
            break
    
    # Look for priority patterns like "priority 8", "P8", "high priority"
    for i, word in enumerate(words):
        if word.lower() in ["priority", "p"] and i + 1 < len(words):
            try:
                priority = int(words[i + 1])
                break
            except ValueError:
                pass
        elif word.lower() == "high":
            priority = 8
        elif word.lower() == "low":
            priority = 3
    
    # Extract title (everything after trigger words until "for" or "priority")
    start_idx = 0
    for i, word in enumerate(words):
        if word.lower() in ["add", "create", "new", "task"]:
            start_idx = i + 1
            break
    
    end_idx = len(words)
    for i, word in enumerate(words[start_idx:], start_idx):
        if word.lower() in ["for", "priority", "p"]:
            end_idx = i
            break
    
    if start_idx < end_idx:
        title = " ".join(words[start_idx:end_idx]).strip(',.')
    
    return title, assignee, priority

def extract_task_id(message):
    """Extract task ID from message."""
    # Look for patterns like "task 5", "#5", "ID 5"
    patterns = [
        r'task\s+(\d+)',
        r'#(\d+)',
        r'id\s+(\d+)',
        r'\b(\d+)\b'  # Any standalone number
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message.lower())
        if match:
            return int(match.group(1))
    return None

def extract_status(message):
    """Extract status from message."""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["todo", "to do", "backlog"]):
        return "todo"
    elif any(word in message_lower for word in ["progress", "doing", "working", "started"]):
        return "in_progress"
    elif any(word in message_lower for word in ["done", "completed", "finished", "complete"]):
        return "done"
    
    return None

def init_db():
    """Initialize SQLite database with enhanced task structure and sprints."""
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # Drop existing tables to recreate with new schema
    cursor.execute('DROP TABLE IF EXISTS tasks')
    cursor.execute('DROP TABLE IF EXISTS sprints')
    
    # Create sprints table
    cursor.execute('''
        CREATE TABLE sprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_date TEXT,
            end_date TEXT,
            is_active BOOLEAN DEFAULT 0
        )
    ''')
    
    # Create enhanced tasks table
    cursor.execute('''
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            assignee TEXT NOT NULL,
            priority INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'todo',
            blocker TEXT,
            sprint_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sprint_id) REFERENCES sprints (id)
        )
    ''')
    
    # Insert sample sprint
    cursor.execute('''
        INSERT INTO sprints (name, start_date, end_date, is_active) 
        VALUES ('Sprint 1 - Q4 Planning', '2024-09-16', '2024-09-30', 1)
    ''')
    sprint_id = cursor.lastrowid
    
    # Insert sample tasks with enhanced structure
    sample_tasks = [
        ('User Authentication System', 'Implement JWT-based login and registration system with password hashing', 'John', 8, 'in_progress', None, sprint_id),
        ('Database Migration Script', 'Create migration scripts for production database schema updates', 'Sarah', 5, 'todo', None, sprint_id),
        ('API Documentation', 'Complete OpenAPI spec and generate interactive docs', 'Mike', 3, 'todo', 'Waiting on API finalization', sprint_id),
        ('Payment Integration', 'Integrate Stripe payment processing for subscriptions', 'Alice', 9, 'in_progress', None, sprint_id),
        ('User Dashboard', 'Build responsive dashboard with charts and analytics', 'Bob', 6, 'done', None, sprint_id),
        ('Email Notifications', 'Set up automated email notifications for key events', 'Carol', 4, 'todo', 'Waiting on email service approval', sprint_id)
    ]
    cursor.executemany('''
        INSERT INTO tasks (title, description, assignee, priority, status, blocker, sprint_id) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', sample_tasks)
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Serve the static HTML page with task table."""
    return render_template('index.html')

@app.route('/board', methods=['GET'])
def get_board():
    """Return current sprint and tasks organized by status."""
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # Get current active sprint
    cursor.execute('SELECT id, name, start_date, end_date FROM sprints WHERE is_active = 1 LIMIT 1')
    sprint_data = cursor.fetchone()
    
    if not sprint_data:
        return jsonify({'error': 'No active sprint found'}), 404
    
    sprint = {
        'id': sprint_data[0],
        'name': sprint_data[1],
        'start_date': sprint_data[2],
        'end_date': sprint_data[3]
    }
    
    # Get all tasks for the current sprint
    cursor.execute('''
        SELECT id, title, description, assignee, priority, status, blocker, created_at 
        FROM tasks WHERE sprint_id = ? ORDER BY priority DESC, created_at ASC
    ''', (sprint['id'],))
    tasks = cursor.fetchall()
    conn.close()
    
    # Organize tasks by status
    board = {
        'sprint': sprint,
        'columns': {
            'todo': [],
            'in_progress': [],
            'done': []
        }
    }
    
    for task in tasks:
        task_obj = {
            'id': task[0],
            'title': task[1],
            'description': task[2],
            'assignee': task[3],
            'priority': task[4],
            'status': task[5],
            'blocker': task[6],
            'created_at': task[7]
        }
        
        if task[5] in board['columns']:
            board['columns'][task[5]].append(task_obj)
    
    return jsonify(board)

@app.route('/add-task', methods=['POST'])
def add_task():
    """Accept JSON task data and insert into current sprint."""
    data = request.get_json()
    
    required_fields = ['title', 'assignee', 'priority']
    if not data or not all(field in data for field in required_fields):
        return jsonify({'error': f'Missing required fields: {", ".join(required_fields)}'}), 400
    
    title = data['title']
    description = data.get('description', '')
    assignee = data['assignee']
    priority = data['priority']
    status = data.get('status', 'todo')
    blocker = data.get('blocker')
    
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # Get current active sprint
    cursor.execute('SELECT id FROM sprints WHERE is_active = 1 LIMIT 1')
    sprint_result = cursor.fetchone()
    
    if not sprint_result:
        conn.close()
        return jsonify({'error': 'No active sprint found'}), 400
    
    sprint_id = sprint_result[0]
    
    cursor.execute('''
        INSERT INTO tasks (title, description, assignee, priority, status, blocker, sprint_id) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (title, description, assignee, priority, status, blocker, sprint_id))
    
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Return the new task
    new_task = {
        'id': task_id,
        'title': title,
        'description': description,
        'assignee': assignee,
        'priority': priority,
        'status': status,
        'blocker': blocker,
        'sprint_id': sprint_id
    }
    
    return jsonify(new_task), 201

@app.route('/update-task-status', methods=['POST'])
def update_task_status():
    """Update task status for drag-and-drop functionality."""
    data = request.get_json()
    
    if not data or 'task_id' not in data or 'status' not in data:
        return jsonify({'error': 'Missing required fields: task_id, status'}), 400
    
    task_id = data['task_id']
    new_status = data['status']
    
    if new_status not in ['todo', 'in_progress', 'done']:
        return jsonify({'error': 'Invalid status. Must be: todo, in_progress, or done'}), 400
    
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE tasks SET status = ? WHERE id = ?', (new_status, task_id))
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'task_id': task_id, 'new_status': new_status})

@app.route('/delete-task/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """Delete a task by ID."""
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'deleted_task_id': task_id})

@app.route('/chat', methods=['POST'])
def chat():
    """Chat endpoint for AI agent to manage tasks."""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        user_message = data['message']
        
        # Use the AI function to process the message
        response = process_ai_request(user_message)
        
        return jsonify({
            'response': response,
            'success': True
        })
    
    except Exception as e:
        return jsonify({
            'error': f'Chat error: {str(e)}',
            'success': False
        }), 500

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=PORT, debug=True)

# Next: Add chatbox to send inputs to a /chat endpoint for AI-powered task management.
# Future AI features:
# - Automatically detect and update blockers
# - Prioritize tasks based on dependencies and deadlines  
# - Ask clarifying questions to better scope tasks
# - Suggest task breakdowns for complex stories
# - Auto-assign tasks based on team member skills and workload
