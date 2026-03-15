# OsteoAI — Clinical Osteoporosis Risk Assessment Platform

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python app.py
```

## Role-Based Access

| Role    | Login → Redirected to    | Can Access                          | Cannot Access             |
|---------|--------------------------|-------------------------------------|---------------------------|
| Patient | /dashboard               | Dashboard, Assessment, History, ... | /doctor/* routes          |
| Doctor  | /doctor/dashboard        | Doctor Dashboard, Patient Records   | /dashboard, /assessment...|

## Features

### Patient Portal
- AI-powered bone density assessment (tabular + X-ray multimodal)
- Grad-CAM heatmap visualization
- Personalized meal plan (vegetarian & non-vegetarian)
- Exercise recommendations with YouTube links
- Floating AI chatbot (bone health Q&A)
- PDF report download
- Health history tracking

### Doctor Portal  
- Separate login with medical license, specialty, hospital fields
- Patient summary dashboard with KPI cards
- Risk distribution pie chart
- Age vs Risk bar chart
- ML model performance chart
- Patient records table with search, filter, CSV export
