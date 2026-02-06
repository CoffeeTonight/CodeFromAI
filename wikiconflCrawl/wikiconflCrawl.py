import asyncio
import json
import re
from typing import List, Dict, Any, Optional
import requests
from atlassian import Confluence  # pip install atlassian-python-api
import mwclient  # pip install mwclient
from crawl4ai import AsyncWebCrawler, BFSDeepCrawlStrategy, CrawlResult  # pip install crawl4ai

class WikiConfluenceCrawler:
    def __init__(self, confluence_url: str, confluence_username: str, confluence_password: str,
                 wiki_url: str, wiki_username: str, wiki_password: str,
                 children_depth: int = 2, linked_depth: int = 2,
                 verify_ssl: bool = False):
        """
        Initialize the crawler.
        - confluence_url: e.g., 'https://your-company.atlassian.net/wiki'
        - wiki_url: e.g., 'https://your-company-wiki.com'
        - For testing, use public sites without auth if possible.
        """
        self.confluence_url = confluence_url
        self.confluence = Confluence(
            url=confluence_url,
            username=confluence_username,
            password=confluence_password,  # API token recommended
            verify_ssl=verify_ssl
        )
        self.wiki_url = wiki_url
        self.wiki_site = mwclient.Site(wiki_url.replace('https://', ''), path='/w/')
        if wiki_username and wiki_password:
            self.wiki_site.login(wiki_username, wiki_password)
        
        self.children_depth = children_depth
        self.linked_depth = linked_depth
        self.tree: Dict[str, Any] = {}
        self.parent_map: Dict[str, str] = {}
        self.visited = set()

    def classify_input(self, s: str) -> Dict[str, Any]:
        """Classify input string as url, id, title."""
        s = s.strip()
        hint = None
        if '#' in s:
            parts = s.split('#', 1)
            s = parts[0].strip()
            if len(parts) > 1:
                hint = parts[1].strip().lower()
        
        if re.match(r'^https?://', s):
            return {"type": "url", "value": s, "hint": hint}
        if re.match(r'^\d+$', s):
            return {"type": "id", "value": s, "hint": hint}
        return {"type": "title", "value": s, "hint": hint}

    def expand_python_list(self, item: str) -> List[str]:
        """Expand Python list code if it's a list expression."""
        item = item.strip()
        if item.startswith('[') and item.endswith(']'):
            try:
                expanded = eval(item, {"__builtins__": {}}, {"range": range})  # Safe eval
                if isinstance(expanded, list):
                    return expanded
            except:
                pass
        return [item]

    async def crawl(self, inputs: List[str]) -> Dict[str, Any]:
        """Main crawl function."""
        flat_inputs = []
        for item in inputs:
            flat_inputs.extend(self.expand_python_list(item))
        
        candidates = [self.classify_input(i) for i in flat_inputs]
        
        for cand in candidates:
            await self.process_candidate(cand)
        
        # Build hierarchy
        def build_hierarchy(url: str) -> Dict:
            node = self.tree.get(url, {})
            children_urls = node.pop("children", [])
            node["children"] = [build_hierarchy(child) for child in children_urls]
            return node
        
        roots = [build_hierarchy(url) for url in self.tree if url not in self.parent_map]
        return {"trees": roots}

    async def process_candidate(self, cand: Dict[str, Any]):
        """Process each input candidate."""
        platform = 'confluence' if cand['hint'] != 'wiki' else 'wiki'
        value = cand['value']
        
        if cand['type'] == 'url':
            await self.crawl_url(value, platform_hint=platform)
        elif cand['type'] == 'id':
            await self.search_by_id(value, platform)
        else:  # title
            await self.search_by_title(value, platform)

    async def search_by_id(self, page_id: str, platform: str):
        if platform == 'confluence' or not platform:
            try:
                page = self.confluence.get_page_by_id(page_id, expand='body.storage,children.page')
                url = f"{self.confluence_url}/pages/{page_id}"
                await self.process_page(page, url, 'confluence')
            except:
                if platform != 'confluence':
                    await self.search_wiki_by_id(page_id)
        else:
            await self.search_wiki_by_id(page_id)

    async def search_wiki_by_id(self, page_id: str):
        params = {'action': 'query', 'pageids': page_id, 'format': 'json'}
        resp = requests.get(f"{self.wiki_url}/w/api.php", params=params)
        data = resp.json()
        if 'pages' in data['query'] and page_id in data['query']['pages']:
            title = data['query']['pages'][page_id]['title']
            url = f"{self.wiki_url}/wiki/{title}"
            await self.process_page({'title': title, 'content': ''}, url, 'wiki')  # Fetch content later

    async def search_by_title(self, title: str, platform: str):
        if platform == 'confluence' or not platform:
            try:
                pages = self.confluence.get_all_pages_by_title(title)
                if pages:
                    page = pages[0]
                    url = f"{self.confluence_url}/pages/{page['id']}"
                    await self.process_page(page, url, 'confluence')
            except:
                if platform != 'confluence':
                    await self.search_wiki_by_title(title)
        else:
            await self.search_wiki_by_title(title)

    async def search_wiki_by_title(self, title: str):
        page = self.wiki_site.pages[title]
        if page.exists:
            url = f"{self.wiki_url}/wiki/{title}"
            content = page.text()  # Markdown-like wikitext
            await self.process_page({'title': title, 'content': content}, url, 'wiki')

    async def crawl_url(self, url: str, platform_hint: Optional[str] = None):
        platform = 'confluence' if 'atlassian' in url or platform_hint == 'confluence' else 'wiki'
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url)
            page = {
                'title': result.title,
                'content': result.markdown,
            }
            await self.process_page(page, url, platform)

    async def process_page(self, page: Dict, url: str, platform: str, depth: int = 0, parent_url: Optional[str] = None):
        if url in self.visited or depth > max(self.children_depth, self.linked_depth):
            return
        
        self.visited.add(url)
        page_id = self.extract_page_id(url)
        node = {
            "url": url,
            "title": page.get('title', 'No title'),
            "page_id": page_id,
            "platform": platform,
            "depth": depth,
            "children": [],
            "content_snippet": page.get('content', '')[:200] + "..."
        }
        self.tree[url] = node
        if parent_url:
            self.tree[parent_url]["children"].append(url)
            self.parent_map[url] = parent_url
        
        # Children and links
        if depth < self.children_depth:
            await self.fetch_children(url, platform, depth)
        if depth < self.linked_depth:
            await self.fetch_links(url, platform, depth)

    def extract_page_id(self, url: str) -> Optional[str]:
        patterns = [r'/pages/(\d+)', r'pageId=(\d+)', r'pageid=(\d+)']
        for p in patterns:
            match = re.search(p, url)
            if match:
                return match.group(1)
        return None

    async def fetch_children(self, url: str, platform: str, depth: int):
        if platform == 'confluence':
            page_id = self.extract_page_id(url)
            if page_id:
                children = self.confluence.get_page_child_by_type(page_id, type='page')
                for child in children.get('results', []):
                    child_url = f"{self.confluence_url}/pages/{child['id']}"
                    child_page = self.confluence.get_page_by_id(child['id'], expand='body.storage')
                    await self.process_page(child_page, child_url, 'confluence', depth + 1, url)
        else:  # wiki subpages
            title = self.tree[url]['title']
            subpages = list(self.wiki_site.pages[title].categories())  # Or subpages via API
            for sub in subpages[:5]:  # Limit for test
                sub_url = f"{self.wiki_url}/wiki/{sub.name}"
                await self.process_page({'title': sub.name, 'content': ''}, sub_url, 'wiki', depth + 1, url)

    async def fetch_links(self, url: str, platform: str, depth: int):
        # Use Crawl4AI for links extraction (cross-platform)
        async with AsyncWebCrawler() as crawler:
            result: CrawlResult = await crawler.arun(url, strategy=BFSDeepCrawlStrategy(max_depth=1))
            for link in result.links[:5]:  # Limit
                link_url = link['href']
                if 'http' in link_url:  # Absolute links
                    link_platform = 'confluence' if 'atlassian' in link_url else 'wiki'
                    await self.process_page({'title': link['text'], 'content': ''}, link_url, link_platform, depth + 1, url)

    def generate_md(self, tree_data: Dict) -> str:
        md = "# Dependency Tree\n```json\n" + json.dumps(tree_data, indent=2, ensure_ascii=False) + "\n```\n\n"
        md += "## Crawled Pages\n"
        for url, node in self.tree.items():
            md += f"### {node['title']} ({node['platform']}, ID: {node['page_id']}, URL: {url})\n"
            md += node['content_snippet'] + "\n\n"
        return md

    def save_outputs(self, tree_data: Dict, md_file: str = 'crawl_result.md'):
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(self.generate_md(tree_data))

if __name__ == '__main__':
    # Placeholder credentials - replace with real ones for private sites
    # For testing, use public sites without auth (comment out username/password)
    crawler = WikiConfluenceCrawler(
        confluence_url='https://confluence.atlassian.com',  # Public Atlassian DOC
        confluence_username='',  # Leave empty for public
        confluence_password='',  # API token if needed
        wiki_url='https://www.mediawiki.org',  # Public MediaWiki
        wiki_username='', 
        wiki_password='',
        children_depth=2,
        linked_depth=2,
        verify_ssl=True  # True for public
    )
    
    # Test inputs: mix of id, title, url, python code for wiki and confluence
    test_inputs = [
        "139501",  # Confluence page ID (Children Display Macro)
        "Help:Subpages",  # Wiki title
        "https://confluence.atlassian.com/doc",  # Confluence URL
        "https://www.mediawiki.org/wiki/Lightbox_demo",  # Wiki URL
        '[f"{i}_test_page" for i in range(3)]',  # Python code expanding to titles
        "12345 #wiki"  # ID with wiki hint
    ]
    
    loop = asyncio.get_event_loop()
    tree_data = loop.run_until_complete(crawler.crawl(test_inputs))
    crawler.save_outputs(tree_data)
    print("Test completed. Check 'crawl_result.md' for output.")