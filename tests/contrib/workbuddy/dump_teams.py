import json

m = json.load(
    open(
        r"D:\AI编程库\项目库\进行中的项目\xiongbao agent\vendor\workbuddy-experts\experts\manifest.json",
        encoding="utf-8",
    )
)
teams = [e for e in m["experts"] if e.get("expertType") == "team"]
print("total team experts:", len(teams))
print()
for t in teams[:8]:
    name = t.get("displayName", {})
    print(f"id={t['id']}  zh={name.get('zh','')}/en={name.get('en','')}")
    print(f"  category={t.get('categoryId')}  plugin={t.get('plugin')}  agentName={t.get('agentName')}")
    tags = [tg.get("zh", "") for tg in t.get("tags", [])]
    print(f"  tags={tags}")
    print(f"  quickPrompts={len(t.get('quickPrompts', []))}")
    print(f"  promptFile={t.get('promptFile')}")
    print()
