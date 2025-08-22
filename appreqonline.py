import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import numpy as np
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(
    page_title="Sistema de Conferência de Requerimentos",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Customizado ---
st.markdown("""
<style>
    /* Estilo do cabeçalho principal */
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
        border-bottom: 3px solid #1f77b4;
        margin-bottom: 2rem;
    }
    /* Estilo dos cartões de métricas */
    .metric-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
        margin-bottom: 1rem;
    }
    /* Estilo dos badges de problema e status */
    .problem-badge {
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.875rem;
        font-weight: bold;
        color: white;
    }
    .qr-badge { background-color: #ff4444; }
    .ch-badge { background-color: #ffbb33; }
    .approved-badge { background-color: #00C851; }
    .rejected-badge { background-color: #ff4444; }
</style>
""", unsafe_allow_html=True)

# --- Função de Autenticação ---
def check_password():
    """Retorna True se o usuário estiver logado, False caso contrário."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # --- Formulário de Login Otimizado ---
    st.title("🔒 Acesso Restrito")
    st.write("Por favor, insira a senha para acessar o sistema.")
    
    # Usando st.form para um envio mais robusto
    with st.form("login_form"):
        # Tenta carregar as senhas do st.secrets (ideal para produção)
        try:
            correct_password = st.secrets["passwords"]["senha_mestra"]
        except (AttributeError, KeyError):
            # Fallback para desenvolvimento local se st.secrets não estiver configurado
            correct_password = "admin" # Senha padrão para teste local

        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")

        if submitted:
            if password == correct_password:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta. Tente novamente.")
    
    return False

# --- Função Principal da Aplicação ---
def run_app():
    # --- Cabeçalho Principal ---
    st.markdown('<h1 class="main-header">📋 Sistema de Conferência de Requerimentos de Matrícula</h1>', unsafe_allow_html=True)

    # --- Sidebar para Upload ---
    with st.sidebar:
        st.header("📁 Upload de Arquivos")
        st.markdown("---")
        file_consolidado = st.file_uploader("**Histórico de Pedidos (consolidado)**", type=["xlsx", "xls"], help="Arquivo: resultado_consolidado.xlsx")
        file_requerimentos = st.file_uploader("**Pedidos do Semestre Atual (requerimentos)**", type=["xlsx", "xls"], help="Arquivo: lista_requerimentos_final.xlsx")
        st.markdown("---")
        st.info("💡 **Dica:** Os arquivos devem conter uma coluna com o número USP para o cruzamento dos dados.")
        with st.expander("⚙️ Configurações Avançadas"):
            show_debug = st.checkbox("Mostrar informações de debug", value=False)
            export_format = st.selectbox("Formato de exportação", ["Excel", "CSV"])

    # --- Lógica Principal ---
    if not (file_consolidado and file_requerimentos):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("""
            ### 🚀 Bem-vindo ao Sistema de Conferência!
            Para começar, faça o upload dos dois arquivos Excel na barra lateral.
            Após o upload, o sistema irá cruzar os dados, identificar alunos com pedidos anteriores, gerar análises e permitir a exportação dos resultados.
            """)
            with st.expander("📋 Estrutura esperada dos arquivos"):
                st.markdown("""
                **Arquivo Consolidado:** `nusp`, `disciplina`, `Ano`, `Semestre`, `problema`, `parecer`
                **Arquivo de Requerimentos:** `nusp`, `Nome completo`
                """)
    else:
        try:
            with st.spinner("Processando arquivos... Por favor, aguarde."):
                df_consolidado = pd.read_excel(file_consolidado)
                df_requerimentos = pd.read_excel(file_requerimentos)
                
                if show_debug:
                    with st.expander("🔍 Debug - Colunas originais"):
                        st.write("**Consolidado:**", df_consolidado.columns.tolist())
                        st.write("**Requerimentos:**", df_requerimentos.columns.tolist())
                        
                df_consolidado = find_and_rename_nusp_column(df_consolidado, ["nusp", "numero usp", "número usp", "n° usp", "n usp"])
                df_requerimentos = find_and_rename_nusp_column(df_requerimentos, ["nusp", "número usp", "numero usp", "n° usp", "n usp"])
                
                validate_dataframes(df_consolidado, df_requerimentos)
                
                for df, nome in [(df_consolidado, "consolidado"), (df_requerimentos, "requerimentos")]:
                    df["nusp"] = pd.to_numeric(df["nusp"], errors='coerce')
                    nulos_antes = df["nusp"].isna().sum()
                    df.dropna(subset=["nusp"], inplace=True)
                    if nulos_antes > 0:
                        st.warning(f"⚠️ Removidos {nulos_antes} registros com NUSP inválido do arquivo {nome}")
                    df["nusp"] = df["nusp"].astype(int)
                
                cols_to_rename = {
                    col: f"{col}_historico" 
                    for col in ['disciplina', 'Ano', 'Semestre', 'problema', 'parecer']
                }
                df_consolidado.rename(columns=cols_to_rename, inplace=True)

                alunos_com_historico = df_requerimentos.merge(
                    df_consolidado,
                    on="nusp",
                    how="inner"
                )
                
                metrics = calculate_additional_metrics(alunos_com_historico)

            # --- Exibição das Métricas Principais ---
            st.markdown("### 📊 Métricas Principais")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total de Requerimentos", len(df_requerimentos), help="Total de pedidos no semestre atual")
            with col2:
                alunos_unicos_historico = alunos_com_historico["nusp"].nunique()
                percentual_historico = (alunos_unicos_historico / df_requerimentos["nusp"].nunique() * 100) if df_requerimentos["nusp"].nunique() > 0 else 0
                st.metric("Alunos com Histórico", alunos_unicos_historico, f"{percentual_historico:.1f}%", help="Alunos que já fizeram pedidos anteriormente")
            with col3:
                total_qr = (alunos_com_historico["problema_historico"].str.upper() == "QR").sum()
                st.metric("Quebras de Requisito", total_qr, help="Total de QR no histórico dos alunos recorrentes")
            with col4:
                total_ch = (alunos_com_historico["problema_historico"].str.upper() == "CH").sum()
                st.metric("Conflitos de Horário", total_ch, help="Total de CH no histórico dos alunos recorrentes")
            with col5:
                taxa_aprovacao = metrics.get('taxa_aprovacao', 0)
                st.metric("Taxa de Aprovação (Hist.)", f"{taxa_aprovacao:.1f}%", help="Percentual de pedidos aprovados no histórico")

            st.markdown("---")

            # --- Análise Detalhada e Visualizações ---
            if not alunos_com_historico.empty:
                st.markdown("### 📈 Análise Gráfica dos Alunos com Histórico")
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.markdown("##### 📚 Top 5 Disciplinas com Histórico")
                    if 'top_disciplinas' in metrics and not metrics['top_disciplinas'].empty:
                        fig = px.bar(metrics['top_disciplinas'], x=metrics['top_disciplinas'].values, y=metrics['top_disciplinas'].index, orientation='h', labels={'x': 'Nº de Pedidos', 'y': 'Disciplina'}, text=metrics['top_disciplinas'].values)
                        fig.update_layout(yaxis={'categoryorder':'total ascending'})
                        st.plotly_chart(fig, use_container_width=True)
                with col_chart2:
                    st.markdown("##### 🗓️ Pedidos por Período")
                    if 'distribuicao_temporal' in metrics and not metrics['distribuicao_temporal'].empty:
                        fig2 = px.line(metrics['distribuicao_temporal'], x=metrics['distribuicao_temporal'].index, y=metrics['distribuicao_temporal'].values, labels={'x': 'Período', 'y': 'Nº de Pedidos'}, markers=True)
                        st.plotly_chart(fig2, use_container_width=True)

                st.markdown("---")
                st.markdown("### 📋 Detalhes por Aluno com Histórico de Pedidos")
                st.info("Clique no nome de um aluno para expandir e ver seu histórico completo de pedidos.")

                df_display = alunos_com_historico.copy()
                alunos_unicos = df_display[['nusp', 'Nome completo']].drop_duplicates().sort_values('Nome completo')

                for _, aluno in alunos_unicos.iterrows():
                    nome_aluno = aluno['Nome completo']
                    nusp_aluno = aluno['nusp']

                    with st.expander(f"� {nome_aluno} (NUSP: {nusp_aluno})"):
                        historico_aluno = df_display[df_display['nusp'] == nusp_aluno].copy()
                        pedidos_deferidos = historico_aluno[historico_aluno['parecer_historico'].str.lower().str.contains('aprovado', na=False)]

                        if not pedidos_deferidos.empty:
                            st.write("##### ✅ Pedidos Deferidos Anteriormente:")
                            cols_deferidos = ['disciplina_historico', 'Ano_historico', 'Semestre_historico', 'parecer_historico']
                            st.dataframe(pedidos_deferidos[cols_deferidos].rename(columns=lambda c: c.replace('_historico', '')).reset_index(drop=True))
                        else:
                            st.info("Este aluno não possui pedidos deferidos no histórico.")

                        st.write("---")
                        st.write("##### 📜 Histórico Completo de Pedidos:")
                        historico_aluno['problema_formatado'] = historico_aluno['problema_historico'].apply(format_problem_type)
                        historico_aluno['parecer_formatado'] = historico_aluno['parecer_historico'].apply(format_parecer)
                        cols_historico_completo = ['disciplina_historico', 'Ano_historico', 'Semestre_historico', 'problema_formatado', 'parecer_formatado']
                        st.dataframe(historico_aluno[cols_historico_completo].rename(columns=lambda c: c.replace('_historico', '').replace('_formatado','')).reset_index(drop=True))

                # --- Funcionalidade de Download ---
                st.markdown("---")
                st.markdown("### 📥 Exportar Relatório Completo")
                
                file_name = f"relatorio_historico_completo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                df_export = alunos_com_historico.copy()
                
                if export_format == "Excel":
                    excel_data = to_excel(df_export)
                    st.download_button("📥 Baixar como Excel", excel_data, f"{file_name}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                else: # CSV
                    csv_data = df_export.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Baixar como CSV", csv_data, f"{file_name}.csv", "text/csv")
            else:
                st.success("✅ Nenhum aluno do semestre atual foi encontrado no histórico de pedidos.")

        except ValueError as e:
            st.error(f"❌ **Erro de Validação:**\n\n{e}\n\nPor favor, verifique a estrutura dos seus arquivos.")
        except Exception as e:
            st.error(f"❌ **Ocorreu um erro inesperado:**\n\n{e}\n\nVerifique se os arquivos estão no formato correto.")
            if show_debug:
                st.exception(e)

# --- Funções Auxiliares (mantidas para referência) ---
def format_problem_type(problem):
    if pd.isna(problem): return "⚪ Não especificado"
    problem = str(problem).upper()
    if problem == "QR": return "🔴 Quebra de Requisito"
    elif problem == "CH": return "🟡 Conflito de Horário"
    return f"⚪ {problem}"

def format_parecer(parecer):
    if pd.isna(parecer): return "📝 Pendente"
    parecer_str = str(parecer).lower()
    if "aprovado" in parecer_str: return f"✅ {parecer}"
    elif "negado" in parecer_str or "indeferido" in parecer_str: return f"❌ {parecer}"
    return f"📝 {parecer}"

@st.cache_data
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio')
        workbook = writer.book
        worksheet = writer.sheets['Relatorio']
        header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'fg_color': '#D7E4BD', 'border': 1})
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        for i, col in enumerate(df.columns):
            column_width = max(df[col].astype(str).map(len).max(), len(str(col))) + 2
            worksheet.set_column(i, i, min(column_width, 50))
    return output.getvalue()

def find_and_rename_nusp_column(df, possible_names):
    normalized_possible_names = [name.lower().strip() for name in possible_names]
    for col in df.columns:
        normalized_col = col.lower().strip()
        if normalized_col in normalized_possible_names or any(keyword in normalized_col for keyword in ['nusp', 'numero usp', 'número usp', 'n° usp']):
            df.rename(columns={col: "nusp"}, inplace=True)
            return df
    raise ValueError(f"Coluna de Número USP não encontrada. Colunas disponíveis: {', '.join(df.columns.tolist())}")

def validate_dataframes(df_consolidado, df_requerimentos):
    required_cols_consolidado = ['nusp']
    required_cols_requerimentos = ['nusp', 'Nome completo']
    
    # Valida colunas renomeadas
    renamed_consolidado_cols = ['disciplina_historico', 'Ano_historico', 'Semestre_historico', 'problema_historico', 'parecer_historico']
    required_cols_consolidado.extend(renamed_consolidado_cols)

    missing_consolidado = [col for col in required_cols_consolidado if col not in df_consolidado.columns]
    missing_requerimentos = [col for col in required_cols_requerimentos if col not in df_requerimentos.columns]
    
    errors = []
    if missing_consolidado: errors.append(f"Arquivo consolidado: colunas faltando - {', '.join(c.replace('_historico', '') for c in missing_consolidado)}")
    if missing_requerimentos: errors.append(f"Arquivo requerimentos: colunas faltando - {', '.join(missing_requerimentos)}")
    if errors: raise ValueError("\n".join(errors))

def calculate_additional_metrics(alunos_com_historico):
    metrics = {}
    if not alunos_com_historico.empty:
        pareceres = alunos_com_historico['parecer_historico'].str.lower()
        aprovados = pareceres.str.contains('aprovado', na=False).sum()
        negados = pareceres.str.contains('negado|indeferido', na=False).sum()
        total_com_parecer = aprovados + negados
        metrics['taxa_aprovacao'] = (aprovados / total_com_parecer * 100) if total_com_parecer > 0 else 0
        metrics['media_pedidos_por_aluno'] = len(alunos_com_historico) / alunos_com_historico['nusp'].nunique()
        metrics['top_disciplinas'] = alunos_com_historico['disciplina_historico'].value_counts().head(5)
        if 'Ano_historico' in alunos_com_historico.columns and 'Semestre_historico' in alunos_com_historico.columns:
            alunos_com_historico['periodo'] = alunos_com_historico['Ano_historico'].astype(str) + '/' + alunos_com_historico['Semestre_historico'].astype(str)
            metrics['distribuicao_temporal'] = alunos_com_historico['periodo'].value_counts().sort_index()
    return metrics

# --- Ponto de Entrada da Aplicação ---
if check_password():
    run_app()
