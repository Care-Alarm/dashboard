#!/usr/bin/env python3
"""
Care-Alarm Organization Dashboard Update Script
Fetches organization repositories, builds, and team info to update the dashboard
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from collections import defaultdict

# GitHub API configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
ORG_NAME = 'Care-Alarm'
API_BASE = 'https://api.github.com'

def get_github_headers():
    """Get headers for GitHub API requests"""
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': f'{ORG_NAME}-dashboard'
    }
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    return headers

def get_org_repositories(limit=10):
    """Fetch organization repositories"""
    url = f'{API_BASE}/orgs/{ORG_NAME}/repos'
    params = {
        'sort': 'pushed',
        'direction': 'desc',
        'per_page': limit,
        'type': 'all'
    }
    
    response = requests.get(url, headers=get_github_headers(), params=params)
    if response.status_code != 200:
        print(f"Error fetching repositories: {response.status_code}")
        return []
    
    return response.json()

def get_org_members():
    """Fetch organization members"""
    url = f'{API_BASE}/orgs/{ORG_NAME}/members'
    response = requests.get(url, headers=get_github_headers())
    if response.status_code != 200:
        return []
    
    return response.json()

def get_workflow_runs(repo_full_name, limit=3):
    """Fetch recent workflow runs for a repository"""
    url = f'{API_BASE}/repos/{repo_full_name}/actions/runs'
    params = {
        'per_page': limit
    }
    
    response = requests.get(url, headers=get_github_headers(), params=params)
    if response.status_code != 200:
        return []
    
    return response.json().get('workflow_runs', [])

def get_repo_releases(repo_full_name, limit=3):
    """Fetch recent releases for a repository"""
    url = f'{API_BASE}/repos/{repo_full_name}/releases'
    params = {'per_page': limit}
    
    response = requests.get(url, headers=get_github_headers(), params=params)
    if response.status_code != 200:
        return []
    
    return response.json()

def format_repository_activity(repos):
    """Format repository activity as markdown"""
    if not repos:
        return "No recent activity found."
    
    activity_md = []
    for repo in repos[:6]:  # Limit to 6 most recent
        name = repo['name']
        description = repo.get('description', 'No description')
        language = repo.get('language', 'Unknown')
        updated = repo['updated_at']
        stars = repo['stargazers_count']
        
        # Parse and format the date
        updated_date = datetime.fromisoformat(updated.replace('Z', '+00:00'))
        time_ago = (datetime.now(updated_date.tzinfo) - updated_date).days
        
        if time_ago == 0:
            time_str = "today"
        elif time_ago == 1:
            time_str = "yesterday"
        else:
            time_str = f"{time_ago} days ago"
        
        emoji = "🔥" if time_ago <= 1 else "📝" if time_ago <= 7 else "📚"
        
        activity_md.append(
            f"{emoji} **[{name}]({repo['html_url']})** "
            f"({language}) - {description[:80]}{'...' if len(description) > 80 else ''}\n"
            f"   ⭐ {stars} stars • Updated {time_str}"
        )
    
    return "\n\n".join(activity_md)

def format_build_status(repos):
    """Format build status information"""
    build_info = []
    
    for repo in repos[:4]:  # Check builds for first 4 repos
        runs = get_workflow_runs(repo['full_name'], 2)
        if not runs:
            continue
            
        repo_builds = []
        for run in runs:
            status_emoji = {
                'success': '✅',
                'failure': '❌',
                'cancelled': '⚠️',
                'in_progress': '🟡'
            }.get(run.get('conclusion') or run.get('status'), '❓')
            
            workflow_name = run['name']
            branch = run['head_branch']
            created_at = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
            time_ago = (datetime.now(created_at.tzinfo) - created_at).days
            
            if time_ago == 0:
                time_str = "today"
            elif time_ago == 1:
                time_str = "yesterday"
            else:
                time_str = f"{time_ago}d ago"
            
            repo_builds.append(f"   {status_emoji} {workflow_name} on `{branch}` • {time_str}")
        
        if repo_builds:
            build_info.append(f"**{repo['name']}**\n" + "\n".join(repo_builds))
    
    return "\n\n".join(build_info) if build_info else "No recent builds found."

def format_team_members(members):
    """Format team members information"""
    if not members:
        return "No team members found."
    
    member_info = []
    for member in members[:8]:  # Limit to 8 members
        login = member['login']
        avatar = member['avatar_url']
        profile = member['html_url']
        member_info.append(f"[<img src='{avatar}' width='30' height='30' alt='{login}'>]({profile})")
    
    return " ".join(member_info)

def format_active_repos(repos):
    """Format active repositories list"""
    if not repos:
        return "No repositories found."
    
    repo_info = []
    for repo in repos:
        name = repo['name']
        language = repo.get('language', 'Unknown')
        stars = repo['stargazers_count']
        
        # Check if repo is private
        visibility = "🔒" if repo['private'] else "🌐"
        
        repo_info.append(f"{visibility} **[{name}]({repo['html_url']})** ({language}) - ⭐ {stars}")
    
    return "\n".join(repo_info)

def format_latest_releases(repos):
    """Format latest releases information"""
    all_releases = []
    
    for repo in repos[:5]:  # Check releases for first 5 repos
        releases = get_repo_releases(repo['full_name'], 2)
        for release in releases:
            release_data = {
                'repo': repo['name'],
                'tag': release['tag_name'],
                'name': release.get('name', release['tag_name']),
                'url': release['html_url'],
                'published_at': release['published_at'],
                'prerelease': release['prerelease']
            }
            all_releases.append(release_data)
    
    # Sort by published date
    all_releases.sort(key=lambda x: x['published_at'], reverse=True)
    
    if not all_releases:
        return "No recent releases found."
    
    release_info = []
    for release in all_releases[:5]:  # Show latest 5 releases
        published_date = datetime.fromisoformat(release['published_at'].replace('Z', '+00:00'))
        time_ago = (datetime.now(published_date.tzinfo) - published_date).days
        
        if time_ago == 0:
            time_str = "today"
        elif time_ago == 1:
            time_str = "yesterday"
        else:
            time_str = f"{time_ago}d ago"
        
        emoji = "🚀" if not release['prerelease'] else "🧪"
        
        release_info.append(
            f"{emoji} **[{release['repo']} {release['tag']}]({release['url']})** - {time_str}"
        )
    
    return "\n".join(release_info)

def format_org_languages(repos):
    """Format organization language statistics"""
    language_stats = defaultdict(int)
    
    for repo in repos:
        if repo.get('language'):
            language_stats[repo['language']] += 1
    
    if not language_stats:
        return "No language data available."
    
    # Sort by usage count
    sorted_languages = sorted(language_stats.items(), key=lambda x: x[1], reverse=True)
    
    lang_info = []
    for language, count in sorted_languages[:8]:  # Top 8 languages
        percentage = (count / len(repos)) * 100
        lang_info.append(f"**{language}** ({count} repos, {percentage:.1f}%)")
    
    return " • ".join(lang_info)

def update_readme():
    """Update the README with fresh organization data"""
    print("🚀 Updating Care-Alarm organization dashboard...")
    
    # Fetch data
    repos = get_org_repositories()
    members = get_org_members()
    
    print(f"📊 Found {len(repos)} repositories and {len(members)} team members")
    
    # Format content
    activity_content = format_repository_activity(repos)
    build_content = format_build_status(repos)
    team_content = format_team_members(members)
    active_repos_content = format_active_repos(repos)
    releases_content = format_latest_releases(repos)
    languages_content = format_org_languages(repos)
    
    # Read current README
    readme_path = 'README.md'
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ {readme_path} not found!")
        return False
    
    # Replace content sections
    replacements = {
        '<!-- RECENT_ACTIVITY:START -->': activity_content,
        '<!-- BUILD_STATUS:START -->': build_content,
        '<!-- TEAM_MEMBERS:START -->': team_content,
        '<!-- ACTIVE_REPOS:START -->': active_repos_content,
        '<!-- LATEST_RELEASES:START -->': releases_content,
        '<!-- ORG_LANGUAGES:START -->': languages_content,
        '<!-- LAST_UPDATED -->': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    }
    
    for marker, replacement in replacements.items():
        if marker in content:
            if marker.endswith('START -->'):
                end_marker = marker.replace('START', 'END')
                start_idx = content.find(marker)
                end_idx = content.find(end_marker)
                
                if start_idx != -1 and end_idx != -1:
                    before = content[:start_idx + len(marker)]
                    after = content[end_idx:]
                    content = f"{before}\n{replacement}\n{after}"
            else:
                content = content.replace(marker, replacement)
    
    # Write updated README
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Care-Alarm dashboard updated successfully!")
    return True

if __name__ == '__main__':
    if not GITHUB_TOKEN:
        print("⚠️  GITHUB_TOKEN environment variable not set. Using public API limits.")
    
    success = update_readme()
    sys.exit(0 if success else 1)