"""
AI Tools for Task Management
Each function represents a tool that the AI agent can use to interact with the task management system.
"""

import sqlite3
import json
from typing import Optional

def tool(description: str):
    """Decorator to mark functions as AI tools."""
    def decorator(func):
        func._is_tool = True
        func._tool_description = description
        func._tool_name = func.__name__
        return func
    return decorator

@tool("Add a new task to the current sprint")
def add_task(title: str, description: str = "", assignee: str = "", priority: int = 5, 
             status: str = "todo", blocker: Optional[str] = None) -> str:
    """
    Add a new task to the current sprint.
    
    Args:
        title: Title of the task (required)
        description: Description of the task (optional)
        assignee: Person assigned to the task (optional)
        priority: Priority level from 1-10 (default: 5)
        status: Task status - todo, in_progress, or done (default: todo)
        blocker: Any blockers for the task (optional)
    
    Returns:
        Success message with task ID or error message
    """
    try:
        conn = sqlite3.connect('tasks.db')
        cursor = conn.cursor()
        
        # Get current active sprint
        cursor.execute('SELECT id FROM sprints WHERE is_active = 1 LIMIT 1')
        sprint_result = cursor.fetchone()
        
        if not sprint_result:
            conn.close()
            return "Error: No active sprint found"
        
        sprint_id = sprint_result[0]
        
        cursor.execute('''
            INSERT INTO tasks (title, description, assignee, priority, status, blocker, sprint_id) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, assignee, priority, status, blocker, sprint_id))
        
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return f"✅ Successfully added task '{title}' with ID {task_id} assigned to {assignee or 'Unassigned'}"
    except Exception as e:
        return f"❌ Error adding task: {str(e)}"

@tool("Update the status of an existing task")
def update_task_status(task_id: int, status: str) -> str:
    """
    Update the status of an existing task.
    
    Args:
        task_id: ID of the task to update
        status: New status - todo, in_progress, or done
    
    Returns:
        Success message or error message
    """
    try:
        if status not in ['todo', 'in_progress', 'done']:
            return "❌ Error: Status must be 'todo', 'in_progress', or 'done'"
        
        conn = sqlite3.connect('tasks.db')
        cursor = conn.cursor()
        
        # Get task info first
        cursor.execute('SELECT title FROM tasks WHERE id = ?', (task_id,))
        task_info = cursor.fetchone()
        
        if not task_info:
            conn.close()
            return f"❌ Error: Task with ID {task_id} not found"
        
        cursor.execute('UPDATE tasks SET status = ? WHERE id = ?', (status, task_id))
        conn.commit()
        conn.close()
        
        status_display = {
            'todo': 'To Do',
            'in_progress': 'In Progress', 
            'done': 'Done'
        }[status]
        
        return f"✅ Successfully moved task '{task_info[0]}' (ID {task_id}) to {status_display}"
    except Exception as e:
        return f"❌ Error updating task: {str(e)}"

@tool("Delete a task by its ID")
def delete_task(task_id: int) -> str:
    """
    Delete a task by its ID.
    
    Args:
        task_id: ID of the task to delete
    
    Returns:
        Success message or error message
    """
    try:
        conn = sqlite3.connect('tasks.db')
        cursor = conn.cursor()
        
        # Get task info first
        cursor.execute('SELECT title FROM tasks WHERE id = ?', (task_id,))
        task_info = cursor.fetchone()
        
        if not task_info:
            conn.close()
            return f"❌ Error: Task with ID {task_id} not found"
        
        cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
        
        return f"🗑️ Successfully deleted task '{task_info[0]}' (ID {task_id})"
    except Exception as e:
        return f"❌ Error deleting task: {str(e)}"

@tool("Get all tasks or filter by status")
def get_tasks(status: Optional[str] = None) -> str:
    """
    Get all tasks or filter by status.
    
    Args:
        status: Filter by status - todo, in_progress, done, or None for all tasks
    
    Returns:
        Formatted list of tasks or error message
    """
    try:
        conn = sqlite3.connect('tasks.db')
        cursor = conn.cursor()
        
        # Get current active sprint
        cursor.execute('SELECT id, name FROM sprints WHERE is_active = 1 LIMIT 1')
        sprint_data = cursor.fetchone()
        
        if not sprint_data:
            conn.close()
            return "❌ Error: No active sprint found"
        
        sprint_id, sprint_name = sprint_data
        
        # Get tasks
        if status:
            cursor.execute('''
                SELECT id, title, description, assignee, priority, status, blocker 
                FROM tasks WHERE sprint_id = ? AND status = ? 
                ORDER BY priority DESC, created_at ASC
            ''', (sprint_id, status))
        else:
            cursor.execute('''
                SELECT id, title, description, assignee, priority, status, blocker 
                FROM tasks WHERE sprint_id = ? 
                ORDER BY priority DESC, created_at ASC
            ''', (sprint_id,))
        
        tasks = cursor.fetchall()
        conn.close()
        
        if not tasks:
            filter_text = f" with status '{status}'" if status else ""
            return f"📋 No tasks found in sprint '{sprint_name}'{filter_text}"
        
        status_emojis = {
            'todo': '📝',
            'in_progress': '🔄',
            'done': '✅'
        }
        
        result = f"📋 **{sprint_name}** ({len(tasks)} tasks)\n\n"
        
        # Group by status for better display
        if not status:
            status_groups = {'todo': [], 'in_progress': [], 'done': []}
            for task in tasks:
                task_status = task[5]
                if task_status in status_groups:
                    status_groups[task_status].append(task)
            
            for status_key, status_tasks in status_groups.items():
                if status_tasks:
                    status_name = {'todo': 'To Do', 'in_progress': 'In Progress', 'done': 'Done'}[status_key]
                    result += f"**{status_emojis[status_key]} {status_name}:**\n"
                    for task in status_tasks:
                        task_id, title, description, assignee, priority, _, blocker = task
                        result += f"  • #{task_id}: {title}"
                        if assignee:
                            result += f" ({assignee})"
                        if priority != 5:
                            result += f" [P{priority}]"
                        if blocker:
                            result += f" 🚫 {blocker}"
                        result += "\n"
                    result += "\n"
        else:
            status_name = {'todo': 'To Do', 'in_progress': 'In Progress', 'done': 'Done'}[status]
            result += f"**{status_emojis[status]} {status_name}:**\n"
            for task in tasks:
                task_id, title, description, assignee, priority, _, blocker = task
                result += f"• #{task_id}: {title}"
                if assignee:
                    result += f" ({assignee})"
                if priority != 5:
                    result += f" [P{priority}]"
                if blocker:
                    result += f" 🚫 {blocker}"
                if description:
                    result += f"\n  📄 {description}"
                result += "\n"
        
        return result.strip()
    except Exception as e:
        return f"❌ Error getting tasks: {str(e)}"

@tool("Get task statistics and summary")
def get_task_stats() -> str:
    """
    Get statistics and summary of all tasks in the current sprint.
    
    Returns:
        Formatted statistics or error message
    """
    try:
        conn = sqlite3.connect('tasks.db')
        cursor = conn.cursor()
        
        # Get current active sprint
        cursor.execute('SELECT id, name FROM sprints WHERE is_active = 1 LIMIT 1')
        sprint_data = cursor.fetchone()
        
        if not sprint_data:
            conn.close()
            return "❌ Error: No active sprint found"
        
        sprint_id, sprint_name = sprint_data
        
        # Get task counts by status
        cursor.execute('''
            SELECT status, COUNT(*) 
            FROM tasks WHERE sprint_id = ? 
            GROUP BY status
        ''', (sprint_id,))
        
        status_counts = dict(cursor.fetchall())
        
        # Get total count
        cursor.execute('SELECT COUNT(*) FROM tasks WHERE sprint_id = ?', (sprint_id,))
        total_tasks = cursor.fetchone()[0]
        
        # Get blocked tasks
        cursor.execute('SELECT COUNT(*) FROM tasks WHERE sprint_id = ? AND blocker IS NOT NULL', (sprint_id,))
        blocked_tasks = cursor.fetchone()[0]
        
        conn.close()
        
        if total_tasks == 0:
            return f"📊 **{sprint_name}**: No tasks yet!"
        
        todo_count = status_counts.get('todo', 0)
        progress_count = status_counts.get('in_progress', 0)
        done_count = status_counts.get('done', 0)
        
        completion_rate = round((done_count / total_tasks) * 100, 1) if total_tasks > 0 else 0
        
        result = f"📊 **Sprint Statistics: {sprint_name}**\n\n"
        result += f"📝 To Do: {todo_count}\n"
        result += f"🔄 In Progress: {progress_count}\n"
        result += f"✅ Done: {done_count}\n"
        result += f"🚫 Blocked: {blocked_tasks}\n\n"
        result += f"📈 **Progress: {completion_rate}%** ({done_count}/{total_tasks} completed)"
        
        return result
    except Exception as e:
        return f"❌ Error getting statistics: {str(e)}"

def get_available_tools():
    """Get all available tools and their descriptions."""
    tools = []
    for name, obj in globals().items():
        if callable(obj) and hasattr(obj, '_is_tool'):
            tools.append({
                'name': obj._tool_name,
                'description': obj._tool_description,
                'function': obj
            })
    return tools

def get_tools_description():
    """Get a formatted description of all available tools."""
    tools = get_available_tools()
    description = "Available AI Tools:\n\n"
    for tool in tools:
        description += f"• {tool['name']}: {tool['description']}\n"
    return description
