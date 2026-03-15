import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import difflib
import random
import os

class AIAssistant:
    def __init__(self):
        # Knowledge Base: (Answer, Category, ImagePath)
        img_path = os.path.join(os.path.dirname(__file__), "assets", "bone_microstructure.png")
        self.knowledge_base = {
            # --- General ---
            "What is osteoporosis?": ("Osteoporosis is a bone disease that occurs when the body loses too much bone, makes too little bone, or both. As a result, bones become weak and may break from a fall or, in serious cases, from sneezing or minor bumps.", "General Info", img_path),
            "What are the symptoms?": ("Osteoporosis is often called a 'silent disease' because you cannot feel your bones weakening. Breaking a bone is often the first sign. Other symptoms include back pain, loss of height over time, and a stooped posture.", "Symptoms", None),
            "Is osteoporosis curable?": ("There is no complete cure, but it can be managed. Proper treatment, including medication, diet, and exercise, can help protect and strengthen your bones.", "Treatment", None),
            "What is the difference between osteopenia and osteoporosis?": ("Osteopenia is where bone density is lower than normal but not low enough to be osteoporosis. It’s a warning sign to take action before it progresses.", "General Info", img_path),
            
            # --- Risk Factors ---
            "What are the risk factors?": ("Risk factors include aging, being female, low body weight, family history, menopause, smoking, excessive alcohol, and long-term use of corticosteroids.", "Risk Factors", None),
            "Can men get osteoporosis?": ("Yes! While more common in women, men can also get osteoporosis, especially after age 70. Risk factors include low testosterone, smoking, and certain medications.", "Demographics", None),
            "Does smoking affect bones?": ("Yes, smoking is bad for your bones. It reduces blood supply to bones, slows the production of bone-forming cells, and decreases the absorption of calcium.", "Lifestyle", None),
            
            # --- Diet & Nutrition ---
            "What foods are good for bones?": ("Top bone-building foods:\n- **Dairy**: Milk, yogurt, cheese.\n- **Green Veggies**: Kale, broccoli, collard greens.\n- **Fish**: Canned salmon/sardines (with bones).\n- **Fortified**: Soymilk, cereal, tofu with calcium.", "Nutrition", None),
            "Does vitamin D help?": ("Yes! Vitamin D is crucial for absorbing calcium. Without it, your body takes calcium from your bones, weakening them. Sources include sunlight, fatty fish, and supplements.", "Nutrition", None),
            "How much calcium do I need?": ("Adults generally need 1,000 mg of calcium per day. Women over 50 and men over 70 should aim for 1,200 mg. Always consult your doctor.", "Nutrition", None),
            "Is caffeine bad for bones?": ("Excessive caffeine (more than 3-4 cups of coffee a day) can slightly interfere with calcium absorption. It's best to enjoy it in moderation.", "Nutrition", None),
            
            # --- Lifestyle & Exercise ---
            "What exercises should I do?": ("The best exercises for bones are **weight-bearing** and **muscle-strengthening** ones:\n- Walking, jogging, dancing, hiking.\n- Lifting weights or using resistance bands.\n- Yoga and Tai Chi for balance (to prevent falls).", "Exercise", None),
            "Can yoga help?": ("Yes! Yoga improves balance and coordination, reducing fall risk. However, avoid deep spine twists or extreme forward bends if you have low bone density.", "Exercise", None),
            "How can I prevent falls?": ("To prevent falls: remove trip hazards (rugs), install grab bars in bathrooms, keep your home well-lit, and do balance exercises like Tai Chi.", "Safety", None),
            
            # --- Medical & Diagnosis ---
            "What is a T-score?": ("A T-score compares your bone density to a healthy 30-year-old:\n- **-1.0 and above**: Normal\n- **-1.0 to -2.5**: Osteopenia (Low bone mass)\n- **-2.5 and below**: Osteoporosis", "Medical Diagnosis", img_path),
            "What is a DEXA scan?": ("A DEXA scan is a quick, painless X-ray that measures bone density. It's the gold standard for diagnosing osteoporosis.", "Medical Diagnosis", None),
            "How often should I get tested?": ("Women over 65 and men over 70 should screen regularly. If you have risk factors (fracture history, steroids), your doctor may test sooner.", "Medical Diagnosis", None),
            "What medications treat osteoporosis?": ("Common treatments include Bisphosphonates (Alendronate), Denosumab, and hormone therapies. Your doctor will choose the best one based on your risk profile.", "Treatment", None)
        }
        
        self.questions = list(self.knowledge_base.keys())
        self.vectorizer = TfidfVectorizer().fit(self.questions)
        self.question_vectors = self.vectorizer.transform(self.questions)

        # Fallback greetings
        self.greetings = ["hi", "hello", "hey", "good morning", "good evening"]

    def get_response(self, user_query):
        """Finds the best matching answer using Hybrid (TF-IDF + Fuzzy) matching."""
        query_lower = user_query.lower().strip()
        
        # 1. Direct Greeting Check
        if any(g in query_lower for g in self.greetings):
            return ("Hello! I am Dr. Bone AI. I can help answer questions about osteoporosis, diet, exercise, and risk factors. Ask away!", "Greeting", None)

        # 2. Keyphrase Shortcuts (Rule-based overrides)
        if "diet" in query_lower or "food" in query_lower or "eat" in query_lower:
            # If vague, give general diet advice
            if len(query_lower) < 15: 
                return self.knowledge_base["What foods are good for bones?"]

        if "exercise" in query_lower or "workout" in query_lower or "gym" in query_lower:
             if len(query_lower) < 15:
                return self.knowledge_base["What exercises should I do?"]

        # 3. TF-IDF Similarity
        user_query_vec = self.vectorizer.transform([user_query])
        similarities = cosine_similarity(user_query_vec, self.question_vectors).flatten()
        best_match_index = np.argmax(similarities)
        score = similarities[best_match_index]
        
        # 4. Fuzzy Matching (Difflib) as backup/validation
        fuzzy_matches = difflib.get_close_matches(user_query, self.questions, n=1, cutoff=0.5)
        
        if score > 0.25:
            return self.knowledge_base[self.questions[best_match_index]]
        elif fuzzy_matches:
            val = self.knowledge_base[fuzzy_matches[0]]
            return (f"Did you mean: **'{fuzzy_matches[0]}'**?\n\n" + val[0], val[1], val[2])
        else:
            return ("I'm sorry, I don't have information on that specific topic yet. "
                    "Try asking about:\n- **Symptoms**\n- **Diet & Foods**\n- **Exercises**\n- **T-Scores**\n- **Risk Factors**", "Unknown", None)

if __name__ == "__main__":
    ai = AIAssistant()
    print(ai.get_response("food"))
