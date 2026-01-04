import streamlit as st
import pandas as pd
from datetime import date, datetime, time, timedelta
from supabase import create_client, Client

# Configuração da página
st.set_page_config(page_title="Rastreador de Metas 2026", layout="wide")
st.title("📈 Rastreador de Metas: BJJ • Leituras • Investimentos")

# Conexão Supabase (use sua SECRET key para bypassar RLS)
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# Função para registrar entrada
def add_entry(category: str, metadata: dict, custom_created_at: datetime | None = None):
    data = {
        "category": category,
        "metadata": metadata
    }
    if custom_created_at:
        data["created_at"] = custom_created_at.isoformat()
    
    supabase.table("habits").insert(data).execute()

# Sidebar - Registro
st.sidebar.header("Nova Atividade")

# Opções do enum (exatamente como no banco)
CATEGORIES = ["BJJ", "Leituras", "Investimentos"]
category = st.sidebar.selectbox("Categoria", options=CATEGORIES)

# Data e hora
today = date.today()
selected_date = st.sidebar.date_input("Data", today)
selected_time = st.sidebar.time_input("Hora", datetime.now().time())
use_custom_date = st.sidebar.checkbox("Usar data/hora personalizada (para registros antigos)", value=False)

custom_created_at = datetime.combine(selected_date, selected_time) if use_custom_date else None

# Campos específicos por categoria
metadata = {}

if category == "BJJ":
    col1, col2 = st.sidebar.columns(2)
    duration = col1.number_input("Duração (min)", min_value=0, value=90, key="bjj_dur")
    rolls = col2.number_input("Rolls", min_value=0, value=6, key="bjj_rolls")
    notes = st.sidebar.text_area("Notas (técnicas, sensação, parceiro...)", key="bjj_notes")
    
    metadata = {
        "duration_min": int(duration),
        "rolls": int(rolls),
        "notes": notes.strip() or None
    }

elif category == "Leituras":
    book = st.sidebar.text_input("Livro", key="read_book")
    pages = st.sidebar.number_input("Páginas lidas", min_value=1, value=20, key="read_pages")
    notes = st.sidebar.text_area("Insights / citações", key="read_notes")
    
    metadata = {
        "book": book.strip(),
        "pages": int(pages),
        "notes": notes.strip() or None
    }

elif category == "Investimentos":
    amount = st.sidebar.number_input("Valor aportado (R$)", min_value=0.01, value=500.0, step=50.0, key="inv_amount")
    asset = st.sidebar.text_input("Ativo (ex: VBBR3, KNRI11, Tesouro Selic)", key="inv_asset")
    notes = st.sidebar.text_area("Motivo / estratégia", key="inv_notes")
    
    metadata = {
        "amount": float(amount),
        "asset": asset.strip(),
        "notes": notes.strip() or None
    }

if st.sidebar.button("Registrar", type="primary"):
    add_entry(category, metadata, custom_created_at)
    st.sidebar.success(f"{category} registrado!")
    st.rerun()

def load_data() -> pd.DataFrame:
    resp = supabase.table("habits").select("*").order("created_at", desc=True).execute()
    df = pd.DataFrame(resp.data)
    if df.empty:
        return df
    
    df['created_at'] = pd.to_datetime(df['created_at'])
    df['date'] = df['created_at'].dt.date
    
    # Extrai quantidade principal para métricas e gráficos
    def get_quantity(row):
        m = row['metadata']
        if row['category'] == 'BJJ':
            return m.get('duration_min', 0)
        elif row['category'] == 'Leituras':
            return m.get('pages', 0)
        elif row['category'] == 'Investimentos':
            return m.get('amount', 0)
        return 0
    
    df['quantity'] = df.apply(get_quantity, axis=1)
    
    # Texto bonito para exibição
    def format_details(row):
        m = row['metadata']
        if row['category'] == 'BJJ':
            return f"{m.get('duration_min', '?')} min • {m.get('rolls', '?')} rolls — {m.get('notes', '')}"
        elif row['category'] == 'Leituras':
            return f"{m.get('book', '?')} • {m.get('pages', '?')} páginas — {m.get('notes', '')}"
        elif row['category'] == 'Investimentos':
            return f"R$ {m.get('amount', 0):,.2f} em {m.get('asset', '?')} — {m.get('notes', '')}"
        return str(m)
    
    df['details'] = df.apply(format_details, axis=1)
    
    return df

df = load_data()

if df.empty:
    st.info("Nenhum registro ainda. Registre sua primeira atividade no menu lateral!")
    st.stop()

# Filtros
st.subheader("Filtros")
col1, col2 = st.columns(2)
start_date = col1.date_input("De", df['date'].min())
end_date = col2.date_input("Até", df['date'].max())
selected_cats = st.multiselect("Categorias", options=CATEGORIES, default=CATEGORIES)

filtered = df[
    (df['date'] >= start_date) &
    (df['date'] <= end_date) &
    (df['category'].isin(selected_cats))
].copy()

# Métricas principais
st.subheader("Resumo do Período")
cols = st.columns(4)
cols[0].metric("Total de registros", len(filtered))

bjj_df = filtered[filtered['category'] == 'BJJ']
if not bjj_df.empty:
    cols[1].metric("Minutos BJJ", f"{bjj_df['quantity'].sum():,.0f}")

read_df = filtered[filtered['category'] == 'Leituras']
if not read_df.empty:
    cols[2].metric("Páginas lidas", f"{read_df['quantity'].sum():,.0f}")

inv_df = filtered[filtered['category'] == 'Investimentos']
if not inv_df.empty:
    cols[3].metric("Total aportado", f"R$ {inv_df['quantity'].sum():,.2f}")

# Gráficos
st.subheader("Progresso")
col1, col2 = st.columns(2)

with col1:
    st.write("Registros por categoria")
    st.bar_chart(filtered['category'].value_counts())

with col2:
    st.write("Atividade diária (quantidade)")
    daily = filtered.groupby(['date', 'category'])['quantity'].sum().unstack(fill_value=0)
    st.line_chart(daily)

# Acumulados
if not inv_df.empty:
    st.write("Aportes acumulados")
    cum_inv = inv_df.sort_values('date')[['date', 'quantity']].set_index('date').cumsum()
    st.line_chart(cum_inv)

if not read_df.empty:
    st.write("Páginas acumuladas")
    cum_read = read_df.sort_values('date')[['date', 'quantity']].set_index('date').cumsum()
    st.line_chart(cum_read)

# Tabela completa
st.subheader("Registros Detalhados")
display_df = filtered[['created_at', 'category', 'details']].copy()
display_df['created_at'] = display_df['created_at'].dt.strftime('%d/%m/%Y %H:%M')
st.dataframe(display_df.sort_values('created_at', ascending=False), use_container_width=True)

# Streaks
st.subheader("🔥 Streaks atuais")
for cat in CATEGORIES:
    if cat in selected_cats:
        dates = sorted(set(filtered[filtered['category'] == cat]['date']))
        if dates:
            streak = 1
            for i in range(len(dates)-2, -1, -1):
                if dates[i+1] - dates[i] == timedelta(days=1):
                    streak += 1
                else:
                    break
            st.write(f"**{cat}**: {streak} dias consecutivos")