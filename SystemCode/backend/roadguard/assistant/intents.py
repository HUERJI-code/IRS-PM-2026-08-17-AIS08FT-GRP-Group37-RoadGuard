"""Conservative, local intent gates; ambiguous questions retain evidence validation."""
import re


def classify_intent(question: str) -> str:
    text = question.strip().lower().rstrip(' ?!\uff1f\uff01\uff0c\u3002.')
    # Match the entire question. A second request must never inherit this shortcut.
    identity = (
        r'(?:what|which) (?:ai |language |llm )?model (?:are you(?: (?:currently )?using)?|do you use)',
        r'\u4f60\u662fgpt(?:\u51e0|\u54ea\u4e00\u4ee3)',
        r'(?:what|which) llm (?:are you|do you use)',
        r'what is your (?:ai |language |llm )?model(?: name)?',
        r'(?:tell me |please tell me )?(?:your |the )(?:configured |current )?(?:ai |language |llm )?model(?: name)?',
        r'\u4f60(?:\u73b0\u5728|\u5f53\u524d)?(?:\u7528\u7684|\u4f7f\u7528\u7684|\u7528|\u4f7f\u7528|\u662f)(?:\u4ec0\u4e48|\u54ea\u4e2a|\u54ea\u79cd)(?:\u5927\u8bed\u8a00|\u8bed\u8a00|ai|\u5927)?\u6a21\u578b',
        r'\u4f60(?:\u73b0\u5728|\u5f53\u524d)?\u662f\u4ec0\u4e48(?:\u5927\u8bed\u8a00|\u8bed\u8a00|ai|\u5927)?\u6a21\u578b',
        r'(?:\u8bf7\u95ee)?\u4f60(?:\u73b0\u5728|\u5f53\u524d)?(?:\u7528\u7684|\u4f7f\u7528\u7684)\u662f(?:\u4ec0\u4e48|\u54ea\u4e2a|\u54ea\u79cd)(?:\u5927\u8bed\u8a00|\u8bed\u8a00|ai|\u5927)?\u6a21\u578b',
    )
    if any(re.fullmatch(pattern, text) for pattern in identity):
        return 'model_info'
    # Explicit unrelated topics only. Domain terms take precedence so mixed or
    # comparative project questions continue through the normal RAG safeguards.
    domain = r'\b(?:roadguard|roads?|potholes?|cracks?|damage|repairs?|routing|routes?|crews?|tasks?|plans?|ga|greedy|yolo\w*|rdd\w*|dataset|model|training|confidence|priority|severity|chroma\w*|embedding|rag|retrieval|rules?|dispatch|deadlines?|durations?|travel|depot|jurong|stops?|schedules?|matrix|matrices|service|sqlite|accounts?|thresholds?)\b|\u7ef4\u4fee|\u4fee\u590d|\u9053\u8def|\u8def\u9762|\u5751\u6d1e|\u88c2\u7f1d|\u635f\u574f|\u8def\u7ebf|\u8def\u7a0b|\u8def\u7531|\u8c03\u5ea6|\u961f\u4f0d|\u68c0\u4fee|\u5de5\u7a0b\u961f|\u4efb\u52a1|\u8ba1\u5212|\u6a21\u578b|\u8bad\u7ec3|\u6570\u636e\u96c6|\u7f6e\u4fe1|\u4f18\u5148|\u4e25\u91cd|\u68c0\u7d22|\u89c4\u5219|\u5de5\u65f6|\u65f6\u95f4|\u7b97\u6cd5|\u77e5\u8bc6\u5e93|\u9879\u76ee|\u7cfb\u7edf'
    if re.search(domain, text):
        return 'grounded'
    unrelated = r'\b(?:world cup|hello|hi|greetings|weather|recipe|cook|cooking|football|soccer|basketball|horoscope|astrology|poem|joke|capital of|president|stock price|bitcoin|movie|song|vacation)\b|\u5929\u6c14|\u83dc\u8c31|\u505a\u996d|\u8db3\u7403|\u7bee\u7403|\u661f\u5ea7|\u5199\u8bd7|\u7b11\u8bdd|\u9996\u90fd|\u603b\u7edf|\u80a1\u7968|\u6bd4\u7279\u5e01|\u7535\u5f71|\u6b4c\u66f2|\u65c5\u6e38'
    return 'out_of_scope' if re.search(unrelated, text) else 'grounded'


SCOPE_GUIDANCE = (
    'I can help with RoadGuard road damage, demo repair priorities and durations, '
    'detection confidence, and saved route plans. Try asking how deep potholes are '
    'prioritized, or select a saved plan and ask about crew visit order. '
    'For other topics, please use a general-purpose assistant.'
)
