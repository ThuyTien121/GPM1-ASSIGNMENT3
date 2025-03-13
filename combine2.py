import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, datetime
import tempfile, os
from fpdf import FPDF

# Constants
CHART_HEIGHT = 600
COLOR_MAP = {
    'Cá nhân Khớp Ròng': '#1f77b4',
    'Nước ngoài Khớp Ròng': '#ff7f0e',
    'Tổ chức trong nước Khớp Ròng': '#2ca02c',
    'Tự doanh Khớp Ròng': '#d62728',
    'Cá nhân Thỏa thuận Ròng': '#1f77b4',
    'Nước ngoài Thỏa thuận Ròng': '#ff7f0e',
    'Tổ chức trong nước Thỏa thuận Ròng': '#2ca02c',
    'Tự doanh Thỏa thuận Ròng': '#d62728'
}

# File paths
VOLUME_PATH = r"E:\MyProject\Vietnam_volume_cleaned.csv"
PRICE_PATH = r"E:\MyProject\Vietnam_Price_cleaned.csv"
SECTOR_PATH = r"E:\MyProject\Phan_loai_nganh.csv"
INVESTOR_DATA_PATH = r"E:\MyProject\combined_data.csv"

# Thiết lập trang
st.set_page_config(page_title="Dashboard Giao dịch Toàn diện", layout="wide")

# Hàm tải và xử lý dữ liệu từ script 1
@st.cache_data
def load_and_prepare_trade_data(volume_path, price_path, sector_path, start_date, end_date):
    start_date = pd.Timestamp(start_date)
    end_date = pd.Timestamp(end_date)

    def read_volume_wide(file_path, start_date, end_date, chunksize=50000):
        chunk_list = []
        for chunk in pd.read_csv(file_path, iterator=True, chunksize=chunksize):
            chunk = chunk.melt(id_vars=['Name', 'Code'], var_name='Date', value_name='Volume')
            chunk['Date'] = pd.to_datetime(chunk['Date'], format='%d-%m-%Y', errors='coerce')
            chunk = chunk[(chunk['Date'] >= start_date) & (chunk['Date'] <= end_date)]
            chunk_list.append(chunk)
        return pd.concat(chunk_list, ignore_index=True) if chunk_list else pd.DataFrame()

    def read_price_wide(file_path, start_date, end_date, chunksize=50000):
        chunk_list = []
        for chunk in pd.read_csv(file_path, iterator=True, chunksize=chunksize):
            chunk = chunk.melt(id_vars=['Name', 'Code'], var_name='Date', value_name='Close')
            chunk['Date'] = pd.to_datetime(chunk['Date'], format='%d-%m-%Y', errors='coerce')
            chunk = chunk[(chunk['Date'] >= start_date) & (chunk['Date'] <= end_date)]
            chunk_list.append(chunk)
        return pd.concat(chunk_list, ignore_index=True) if chunk_list else pd.DataFrame()

    df_volume = read_volume_wide(volume_path, start_date, end_date)
    df_price = read_price_wide(price_path, start_date, end_date)
    df_sector = pd.read_csv(sector_path)
    if 'Mã' in df_sector.columns:
        df_sector.rename(columns={'Mã': 'Code'}, inplace=True)
    
    df_trade = pd.merge(df_price, df_volume, on=['Date', 'Code'], how='inner')
    df_trade = pd.merge(df_trade, df_sector, on='Code', how='left')
    df_trade['TradeValue'] = df_trade['Close'] * df_trade['Volume'] / 1e9
    df_trade.dropna(subset=['TradeValue'], inplace=True)
    if 'Ngành ICB - cấp 1' in df_trade.columns:
        df_trade.rename(columns={'Ngành ICB - cấp 1': 'Industry'}, inplace=True)
    return df_trade

# Hàm tải dữ liệu từ script 2
@st.cache_data
def load_investor_data():
    df = pd.read_csv(INVESTOR_DATA_PATH)
    df['Date'] = pd.to_datetime(df['Date'])
    df.rename(columns={'Ngành': 'Industry'}, inplace=True)
    return df

# Hàm lọc dữ liệu theo ngày
def filter_data_by_date(df, start_date, end_date):
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    return df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]

# Hàm tạo PDF từ nhiều biểu đồ
def export_charts_to_pdf(charts):
    with tempfile.TemporaryDirectory() as tmpdirname:
        image_paths = []
        for name, fig in charts.items():
            img_path = os.path.join(tmpdirname, f"{name}.png")
            fig.write_image(img_path, format="png")
            image_paths.append(img_path)
        pdf = FPDF()
        for img_path in image_paths:
            pdf.add_page()
            pdf.image(img_path, x=10, y=10, w=pdf.w - 20)
        pdf_output = pdf.output(dest="S").encode("latin1")
        return pdf_output

# Hàm chuẩn bị dữ liệu cho biểu đồ khớp/thỏa thuận
def prepare_investor_data(filtered_df, transaction_type="Khớp"):
    prefix = "Khớp" if transaction_type == "Khớp" else "Thỏa thuận"
    cols = [f'Cá nhân {prefix} Ròng', f'Nước ngoài {prefix} Ròng', 
            f'Tổ chức trong nước {prefix} Ròng', f'Tự doanh {prefix} Ròng']
    investor_data = filtered_df.groupby('Industry')[cols].sum().reset_index()
    investor_data['Tổng'] = investor_data[cols].sum(axis=1)
    investor_data = investor_data.sort_values(by='Tổng', ascending=False)
    return pd.melt(
        investor_data,
        id_vars=['Industry'],
        value_vars=cols,
        var_name='Nhà đầu tư',
        value_name='Giá trị'
    )

# Hàm tạo biểu đồ cột chồng
def create_stacked_bar_chart(data, title, height=CHART_HEIGHT):
    fig = px.bar(
        data, x='Giá trị', y='Industry', color='Nhà đầu tư', orientation='h',
        title=title, color_discrete_map=COLOR_MAP
    )
    fig.update_layout(
        height=height, barmode='stack', xaxis_title="Giá trị giao dịch (VND)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=200)
    )
    return fig

# Sidebar
st.sidebar.title("Điều hướng và Cài đặt")
page = st.sidebar.radio("Chọn trang:", ("Tổng quan", "Chi tiết"))

st.sidebar.header("Chọn khoảng thời gian")
today = datetime(2025, 3, 12)
default_start = today - pd.Timedelta(days=30)
default_end = today
start_date = st.sidebar.date_input("Ngày bắt đầu", value=default_start)
end_date = st.sidebar.date_input("Ngày kết thúc", value=default_end)
if start_date > end_date:
    st.sidebar.error("Ngày bắt đầu không được lớn hơn ngày kết thúc!")
    st.stop()

# Hiển thị chọn biểu đồ chỉ trên trang "Tổng quan"
if page == "Tổng quan":
    st.sidebar.header("Chọn biểu đồ")
    show_chart1 = st.sidebar.checkbox("GTD(B) & % thay đổi theo ngày", value=True)
    show_chart2 = st.sidebar.checkbox("Top 15 cổ phiếu (ngày mới nhất)", value=True)
    show_chart3 = st.sidebar.checkbox("Top 6 ngành (ngày mới nhất)", value=True)
    show_chart4 = st.sidebar.checkbox("Bubble Chart theo nhóm ngành", value=True)
    show_chart5 = st.sidebar.checkbox("Sức mạnh ngành theo thời gian", value=True)
    show_khop = st.sidebar.checkbox("Giao dịch Khớp Ròng", value=True)
    show_thoathuan = st.sidebar.checkbox("Giao dịch Thỏa thuận Ròng", value=True)

# Load data
df_trade = load_and_prepare_trade_data(VOLUME_PATH, PRICE_PATH, SECTOR_PATH, start_date, end_date)
df_investor = load_investor_data()
filtered_trade = filter_data_by_date(df_trade, start_date, end_date)
filtered_investor = filter_data_by_date(df_investor, start_date, end_date)

# Main content
charts = {}

def overview_page():
    st.title("TỔNG QUAN GIAO DỊCH")
    
    if show_chart1:
        st.markdown("### 1) GTD(B) & % thay đổi theo ngày")
        daily_value = filtered_trade.groupby('Date')['TradeValue'].sum().reset_index().sort_values('Date')
        daily_value['pct_change'] = daily_value['TradeValue'].pct_change() * 100
        daily_value['pct_change'].fillna(0, inplace=True)
        daily_value['Date_str'] = daily_value['Date'].dt.strftime('%Y-%m-%d')
        fig1 = make_subplots(specs=[[{"secondary_y": True}]])
        fig1.add_trace(go.Bar(x=daily_value['Date_str'], y=daily_value['TradeValue'], name="GTD(B)", marker_color='skyblue'), secondary_y=False)
        fig1.add_trace(go.Scatter(x=daily_value['Date_str'], y=daily_value['pct_change'], name="% thay đổi", mode='lines+markers', marker_color='orange'), secondary_y=True)
        fig1.update_layout(title="GTD(B) theo ngày & % thay đổi", template='plotly_white', hovermode="x unified")
        fig1.update_xaxes(title_text="Ngày", type='category')
        fig1.update_yaxes(title_text="GTD(B) (tỷ đồng)", secondary_y=False)
        fig1.update_yaxes(title_text="% thay đổi", secondary_y=True)
        st.plotly_chart(fig1, use_container_width=True)
        charts['chart1'] = fig1

    if show_chart2:
        st.markdown("### 2) Top 15 cổ phiếu (ngày mới nhất) với % thay đổi")
        latest_date = filtered_trade['Date'].max()
        df_latest = filtered_trade[filtered_trade['Date'] == latest_date]
        code_latest = df_latest.groupby('Code', as_index=False)['TradeValue'].sum()
        
        def compute_pct_change(code):
            mask = (filtered_trade['Code'] == code) & (filtered_trade['Date'] < latest_date)
            prev_data = filtered_trade[mask]
            if prev_data.empty or prev_data['TradeValue'].sum() == 0:
                return 0
            latest_value = code_latest.loc[code_latest['Code'] == code, 'TradeValue'].values[0]
            prev_value = prev_data['TradeValue'].sum()
            return (latest_value - prev_value) / prev_value * 100

        code_latest['pct_change'] = code_latest['Code'].apply(compute_pct_change)
        top_15 = code_latest.nlargest(15, 'TradeValue')
        fig2 = px.bar(top_15, x='Code', y='TradeValue', color='Code', text=top_15['pct_change'].apply(lambda x: f"{x:.2f}%"), 
                      title=f"Top 15 cổ phiếu (ngày {latest_date.date()})", template='plotly_dark')
        fig2.update_traces(textposition='outside')
        fig2.update_layout(xaxis_title="Mã cổ phiếu", yaxis_title="Giá trị giao dịch (tỷ đồng)")
        st.plotly_chart(fig2, use_container_width=True)
        charts['chart2'] = fig2

    if show_chart3:
        st.markdown("### 3) Top 6 ngành (ngày mới nhất) với % thay đổi")
        latest_date = filtered_trade['Date'].max()
        df_latest = filtered_trade[filtered_trade['Date'] == latest_date]
        if 'Industry' in df_latest.columns:
            ind_latest = df_latest.groupby('Industry', as_index=False)['TradeValue'].sum()
            
            def compute_pct_change_ind(ind):
                mask = (filtered_trade['Industry'] == ind) & (filtered_trade['Date'] < latest_date)
                prev_data = filtered_trade[mask]
                if prev_data.empty or prev_data['TradeValue'].sum() == 0:
                    return 0
                latest_value = ind_latest.loc[ind_latest['Industry'] == ind, 'TradeValue'].values[0]
                prev_value = prev_data['TradeValue'].sum()
                return (latest_value - prev_value) / prev_value * 100
            
            ind_latest['pct_change'] = ind_latest['Industry'].apply(compute_pct_change_ind)
            top_6 = ind_latest.nlargest(6, 'TradeValue')
            fig3 = px.bar(top_6, x='Industry', y='TradeValue', color='Industry', text=top_6['pct_change'].apply(lambda x: f"{x:.2f}%"), 
                          title=f"Top 6 ngành (ngày {latest_date.date()})", template='plotly_dark')
            fig3.update_traces(textposition='outside')
            fig3.update_layout(xaxis_title="Ngành", yaxis_title="Giá trị giao dịch (tỷ đồng)")
            st.plotly_chart(fig3, use_container_width=True)
            charts['chart3'] = fig3

    if show_chart4:
        st.markdown("### 4) Bubble Chart theo nhóm ngành (Top 5 cổ phiếu/nhóm)")
        latest_date = filtered_trade['Date'].max()
        df_latest = filtered_trade[filtered_trade['Date'] == latest_date]
        if 'Industry' in df_latest.columns:
            df_ind_code = df_latest.groupby(['Industry', 'Code'], as_index=False)['TradeValue'].sum()
            df_top_by_ind = df_ind_code.groupby('Industry', group_keys=True).apply(lambda g: g.nlargest(5, 'TradeValue')).reset_index(drop=True)
            
            def compute_pct_change(code):
                mask = (filtered_trade['Code'] == code) & (filtered_trade['Date'] < latest_date)
                prev_data = filtered_trade[mask]
                if prev_data.empty or prev_data['TradeValue'].sum() == 0:
                    return 0
                latest_value = df_top_by_ind.loc[df_top_by_ind['Code'] == code, 'TradeValue'].values[0]
                prev_value = prev_data['TradeValue'].sum()
                return (latest_value - prev_value) / prev_value * 100
            
            df_top_by_ind['pct_change'] = df_top_by_ind['Code'].apply(compute_pct_change)
            df_top_by_ind['ChangeStatus'] = np.where(df_top_by_ind['pct_change'] >= 0, 'Tăng', 'Giảm')
            unique_inds = df_top_by_ind['Industry'].unique()
            mapping = {ind: i for i, ind in enumerate(unique_inds)}
            df_top_by_ind['x'] = df_top_by_ind['Industry'].map(mapping) + np.random.rand(len(df_top_by_ind)) * 0.8
            df_top_by_ind['y'] = np.random.rand(len(df_top_by_ind)) * 10
            fig4 = px.scatter(df_top_by_ind, x='x', y='y', size='TradeValue', color='ChangeStatus', 
                              color_discrete_map={'Tăng': 'green', 'Giảm': 'red'}, hover_name='Code', 
                              hover_data={'TradeValue': True, 'Industry': True, 'pct_change': ':.2f'}, size_max=60,
                              title=f"Bubble Chart ngành (ngày {latest_date.date()})", template='plotly_dark')
            fig4.update_layout(xaxis={'visible': False}, yaxis={'visible': False})
            st.plotly_chart(fig4, use_container_width=True)
            charts['chart4'] = fig4

    if show_chart5:
        st.markdown("### 5) Sức mạnh ngành theo thời gian")
        if 'Industry' in filtered_trade.columns:
            df_industry_daily = filtered_trade.groupby(['Date', 'Industry'], as_index=False)['TradeValue'].sum()
            df_total_daily = filtered_trade.groupby('Date', as_index=False)['TradeValue'].sum()
            df_total_daily.rename(columns={'TradeValue': 'TotalValue'}, inplace=True)
            df_industry_daily = pd.merge(df_industry_daily, df_total_daily, on='Date', how='left')
            df_industry_daily['Share'] = df_industry_daily['TradeValue'] / df_industry_daily['TotalValue']
            pivot_share = df_industry_daily.pivot(index='Date', columns='Industry', values='Share').fillna(0)
            pivot_share.index = pivot_share.index.strftime('%Y-%m-%d')
            fig5 = px.line(pivot_share, x=pivot_share.index, y=pivot_share.columns, 
                           title="Sức mạnh ngành theo thời gian", template="plotly_dark")
            fig5.update_layout(xaxis_title="Ngày", yaxis_title="Thị phần (%)", legend_title="Ngành")
            st.plotly_chart(fig5, use_container_width=True)
            charts['chart5'] = fig5

    if show_khop:
        st.markdown("### 6) Giao dịch Khớp Ròng theo ngành và nhà đầu tư")
        khop_data_melted = prepare_investor_data(filtered_investor, "Khớp")
        fig_khop = create_stacked_bar_chart(khop_data_melted, 'Giao dịch Khớp lệnh ròng theo Ngành và Nhà đầu tư')
        st.plotly_chart(fig_khop, use_container_width=True)
        charts['khop'] = fig_khop
        if st.button("Xuất PDF biểu đồ khớp"):
            temp_charts = {'khop': fig_khop}
            pdf_output = export_charts_to_pdf(temp_charts)
            st.download_button(
                label="Download PDF",
                data=pdf_output,
                file_name="giaodich_khop.pdf",
                mime="application/pdf"
            )

    if show_thoathuan:
        st.markdown("### 7) Giao dịch Thỏa thuận Ròng theo ngành và nhà đầu tư")
        thoathuan_data_melted = prepare_investor_data(filtered_investor, "Thỏa thuận")
        fig_thoathuan = create_stacked_bar_chart(thoathuan_data_melted, 'Giao dịch Thỏa thuận ròng theo Ngành và Nhà đầu tư')
        st.plotly_chart(fig_thoathuan, use_container_width=True)
        charts['thoathuan'] = fig_thoathuan
        if st.button("Xuất PDF biểu đồ thỏa thuận"):
            temp_charts = {'thoathuan': fig_thoathuan}
            pdf_output = export_charts_to_pdf(temp_charts)
            st.download_button(
                label="Download PDF",
                data=pdf_output,
                file_name="giaodich_thoathuan.pdf",
                mime="application/pdf"
            )

    if st.sidebar.button("Export Selected Charts to PDF"):
        if charts:
            pdf_output = export_charts_to_pdf(charts)
            st.download_button(
                label="Download PDF",
                data=pdf_output,
                file_name="all_charts.pdf",
                mime="application/pdf"
            )
        else:
            st.sidebar.warning("Không có biểu đồ nào được chọn để xuất!")

def detail_page():
    st.title("CHI TIẾT GIAO DỊCH")
    group_option = st.sidebar.selectbox("Chọn nhóm giao dịch", ("Cá nhân", "Nước ngoài", "Tổ chức", "Tự doanh"))
    chart_option = st.sidebar.radio("Chọn loại biểu đồ", ("Khớp", "Thỏa thuận"))
    column = f"{group_option} {chart_option} Ròng" if group_option != "Tổ chức" else f"Tổ chức trong nước {chart_option} Ròng"
    
    df_grouped = filtered_investor.groupby('Industry')[column].sum().reset_index()
    df_grouped = df_grouped.sort_values(by=column)
    fig_detail = px.bar(df_grouped, x=column, y='Industry', color='Industry', 
                        title=f'Giao dịch theo Ngành và {group_option} ({chart_option})',
                        labels={column: f'{group_option} ({chart_option}) (VND)', 'Industry': 'Ngành'})
    st.plotly_chart(fig_detail, use_container_width=True)
    charts['detail'] = fig_detail

    if st.button("Xuất biểu đồ chi tiết ra PDF"):
        temp_charts = {'detail': fig_detail}
        pdf_output = export_charts_to_pdf(temp_charts)
        st.download_button(
            label="Download PDF",
            data=pdf_output,
            file_name=f"{group_option}_{chart_option}.pdf",
            mime="application/pdf"
        )

    if st.checkbox("Hiển thị dữ liệu thô"):
        st.subheader("Dữ liệu gốc")
        st.dataframe(filtered_investor)

    st.subheader("Thống kê tổng quát")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Tổng số ngành", filtered_investor['Industry'].nunique())
    with col2:
        total_value = filtered_investor[column].sum()
        st.metric(f"Tổng {group_option} ({chart_option}) Ròng", f"{total_value:,.0f} VND")

# Main execution
if page == "Tổng quan":
    overview_page()
else:
    detail_page()