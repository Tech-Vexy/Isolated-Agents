"""REST API integration with error handling and rate limiting.

This example demonstrates:
- Making HTTP requests to REST APIs
- Authentication with API keys
- Error handling and retries
- Rate limiting
- Response validation
- Data transformation

Usage:
    export API_KEY=your_api_key_here
    python examples/scenarios/api_integration/rest_api_agent.py
"""

import os
import sys
from pathlib import Path


def rest_api_agent():
    """Interact with REST APIs safely and reliably."""
    import requests
    from pathlib import Path
    import json
    from datetime import datetime
    import time
    from typing import Dict, Any, Optional
    
    print("Starting REST API integration agent...")
    
    class APIClient:
        """Simple API client with retry logic and rate limiting."""
        
        def __init__(self, base_url: str, api_key: Optional[str] = None):
            self.base_url = base_url.rstrip('/')
            self.api_key = api_key
            self.session = requests.Session()
            
            if api_key:
                self.session.headers.update({
                    'Authorization': f'Bearer {api_key}'
                })
            
            self.session.headers.update({
                'User-Agent': 'Isolated-Agents-SDK/0.2.1',
                'Accept': 'application/json'
            })
        
        def get(self, endpoint: str, params: Optional[Dict] = None, 
                max_retries: int = 3) -> Dict[str, Any]:
            """Make GET request with retry logic."""
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            
            for attempt in range(max_retries):
                try:
                    print(f"  GET {url} (attempt {attempt + 1}/{max_retries})")
                    response = self.session.get(url, params=params, timeout=10)
                    response.raise_for_status()
                    
                    # Rate limiting - be nice to APIs
                    time.sleep(0.5)
                    
                    return response.json()
                    
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:  # Rate limited
                        wait_time = int(e.response.headers.get('Retry-After', 5))
                        print(f"  Rate limited, waiting {wait_time}s...")
                        time.sleep(wait_time)
                    elif e.response.status_code >= 500:  # Server error
                        if attempt < max_retries - 1:
                            wait_time = 2 ** attempt  # Exponential backoff
                            print(f"  Server error, retrying in {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            raise
                    else:
                        raise
                        
                except requests.exceptions.Timeout:
                    if attempt < max_retries - 1:
                        print(f"  Timeout, retrying...")
                        time.sleep(1)
                    else:
                        raise
                        
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        print(f"  Request failed: {e}, retrying...")
                        time.sleep(1)
                    else:
                        raise
            
            raise Exception(f"Failed after {max_retries} attempts")
        
        def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
            """Make POST request."""
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            print(f"  POST {url}")
            
            response = self.session.post(url, json=data, timeout=10)
            response.raise_for_status()
            
            time.sleep(0.5)  # Rate limiting
            
            return response.json()
    
    try:
        # Example 1: JSONPlaceholder API (free, no auth required)
        print("\n=== Example 1: Fetching Posts ===")
        client = APIClient("https://jsonplaceholder.typicode.com")
        
        # Fetch posts
        posts = client.get("posts", params={"_limit": 5})
        print(f"✓ Fetched {len(posts)} posts")
        
        # Fetch specific post
        post = client.get("posts/1")
        print(f"✓ Fetched post: {post.get('title', 'N/A')}")
        
        # Fetch comments for post
        comments = client.get("posts/1/comments")
        print(f"✓ Fetched {len(comments)} comments")
        
        # Example 2: Create new post
        print("\n=== Example 2: Creating Post ===")
        new_post = {
            "title": "Test Post from Isolated Agent",
            "body": "This post was created by an isolated agent",
            "userId": 1
        }
        
        created_post = client.post("posts", new_post)
        print(f"✓ Created post with ID: {created_post.get('id')}")
        
        # Example 3: Fetch users
        print("\n=== Example 3: Fetching Users ===")
        users = client.get("users", params={"_limit": 3})
        print(f"✓ Fetched {len(users)} users")
        
        for user in users:
            print(f"  • {user.get('name')} ({user.get('email')})")
        
        # Example 4: Data aggregation
        print("\n=== Example 4: Data Aggregation ===")
        all_posts = client.get("posts")
        
        # Aggregate by user
        posts_by_user = {}
        for post in all_posts:
            user_id = post['userId']
            if user_id not in posts_by_user:
                posts_by_user[user_id] = []
            posts_by_user[user_id].append(post)
        
        print(f"✓ Aggregated {len(all_posts)} posts from {len(posts_by_user)} users")
        
        # Find most active user
        most_active_user = max(posts_by_user.items(), key=lambda x: len(x[1]))
        print(f"  Most active user: User {most_active_user[0]} with {len(most_active_user[1])} posts")
        
        # Prepare outputs
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save posts
        posts_path = output_dir / "posts.json"
        with open(posts_path, 'w') as f:
            json.dump(posts, f, indent=2)
        print(f"\n✓ Saved: {posts_path.name}")
        
        # Save users
        users_path = output_dir / "users.json"
        with open(users_path, 'w') as f:
            json.dump(users, f, indent=2)
        print(f"✓ Saved: {users_path.name}")
        
        # Save aggregated data
        aggregation_path = output_dir / "posts_by_user.json"
        # Convert to serializable format
        aggregation_data = {
            str(user_id): [p['title'] for p in posts]
            for user_id, posts in posts_by_user.items()
        }
        with open(aggregation_path, 'w') as f:
            json.dump(aggregation_data, f, indent=2)
        print(f"✓ Saved: {aggregation_path.name}")
        
        # Create summary report
        report = f"""# REST API Integration Report

Generated: {datetime.now().isoformat()}

## API Endpoints Used

1. **GET /posts** - Fetched {len(all_posts)} posts
2. **GET /posts/1** - Fetched specific post
3. **GET /posts/1/comments** - Fetched {len(comments)} comments
4. **POST /posts** - Created new post (ID: {created_post.get('id')})
5. **GET /users** - Fetched {len(users)} users

## Statistics

- **Total Posts**: {len(all_posts)}
- **Total Users**: {len(posts_by_user)}
- **Average Posts per User**: {len(all_posts) / len(posts_by_user):.1f}
- **Most Active User**: User {most_active_user[0]} ({len(most_active_user[1])} posts)

## Sample Post

**Title**: {post.get('title')}
**Body**: {post.get('body')[:100]}...
**User ID**: {post.get('userId')}

## Sample Users

"""
        
        for user in users[:3]:
            report += f"\n### {user.get('name')}\n"
            report += f"- **Email**: {user.get('email')}\n"
            report += f"- **Company**: {user.get('company', {}).get('name', 'N/A')}\n"
            report += f"- **Website**: {user.get('website', 'N/A')}\n"
        
        report += f"""

## API Client Features

✓ Automatic retry logic with exponential backoff
✓ Rate limiting (0.5s between requests)
✓ Timeout handling (10s per request)
✓ HTTP error handling
✓ 429 (Rate Limit) detection and handling
✓ Server error (5xx) retry logic

## Files Generated

- `posts.json` - Sample posts
- `users.json` - User data
- `posts_by_user.json` - Aggregated data
- `report.md` - This report
- `metadata.json` - Execution metadata
"""
        
        report_path = output_dir / "report.md"
        report_path.write_text(report)
        print(f"✓ Saved: {report_path.name}")
        
        # Save metadata
        metadata = {
            "executed_at": datetime.now().isoformat(),
            "api_base_url": "https://jsonplaceholder.typicode.com",
            "total_requests": 6,
            "total_posts_fetched": len(all_posts),
            "total_users_fetched": len(users),
            "total_comments_fetched": len(comments),
            "post_created_id": created_post.get('id'),
            "most_active_user_id": most_active_user[0],
            "most_active_user_posts": len(most_active_user[1])
        }
        
        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"✓ Saved: {metadata_path.name}")
        
        print("\n✓ API integration completed successfully")
        
        return f"Processed {len(all_posts)} posts from {len(users)} users"
        
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        print(f"✗ {error_msg}")
        
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "error.txt").write_text(error_msg)
        
        raise
        
    except Exception as e:
        error_msg = f"Agent failed: {str(e)}"
        print(f"✗ {error_msg}")
        
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "error.txt").write_text(error_msg)
        
        raise


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
    
    # Setup directories
    output = Path("./output/api_integration")
    output.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("REST API Integration Agent")
    print("=" * 70)
    print()
    print("This example demonstrates safe API integration with:")
    print("  • Automatic retry logic")
    print("  • Rate limiting")
    print("  • Error handling")
    print("  • Network isolation")
    print()
    
    # Configure policy
    policy = Policy(
        cpu_cores=1.0,
        memory_mb=1024,
        timeout_seconds=120,
        
        # Network access restricted to specific API
        network=NetworkPolicy(
            disabled=False,
            allowed_endpoints=[
                "jsonplaceholder.typicode.com:443"
            ]
        ),
        
        # API key if needed (optional for this example)
        allowed_env_vars=["API_KEY"],
        
        pip_packages=["requests"]
    )
    
    print("Launching agent in isolated container...")
    print()
    
    # Run agent
    result = run_agent(
        agent=rest_api_agent,
        working_dir="./workspace",
        host_output_path=output,
        policy=policy
    )
    
    print()
    print("=" * 70)
    
    if result.exit_code == 0:
        print("✓ API integration completed successfully")
        print()
        
        if result.artifacts:
            print("Generated artifacts:")
            for name, path in result.artifacts.items():
                file_path = Path(path)
                if file_path.exists():
                    size = file_path.stat().st_size
                    print(f"  • {name} ({size:,} bytes)")
            
            # Show report location
            report_path = result.artifacts.get("report.md")
            if report_path:
                print()
                print(f"Full report available at: {report_path}")
    else:
        print(f"✗ API integration failed with exit code {result.exit_code}")
        if result.error:
            print(f"Error: {result.error}")
    
    print("=" * 70)
    
    sys.exit(result.exit_code)
