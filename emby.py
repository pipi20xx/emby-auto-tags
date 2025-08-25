
import sys
import requests
import json
import logging
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTextBrowser, QMessageBox, QCheckBox
)
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from datetime import timedelta

CONFIG_FILE = 'emby_searcher_config.json'

# --- 日志设置 ---
log = logging.getLogger('emby_searcher')
log.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# --- 用于线程的 Worker 类 (已修改为 SearchWorker) ---
class SearchWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, server_url, api_key, tmdb_id_str, search_movies, search_series, show_raw_json):
        super().__init__()
        self.server_url = server_url.strip()
        self.api_key = api_key.strip()
        self.tmdb_id_str = tmdb_id_str.strip()
        self.search_movies = search_movies
        self.search_series = search_series
        self.show_raw_json = show_raw_json
        self.session = requests.Session()
        self.search_url_base = f"{self.server_url.rstrip('/')}/emby/Items"

    def _emby_headers(self):
        return {'X-Emby-Token': self.api_key, 'Content-Type': 'application/json'}

    def _format_runtime(self, ticks):
        if ticks is None:
            return "N/A"
        try:
            seconds = ticks / 10000000
            return str(timedelta(seconds=int(seconds)))
        except:
            return "N/A"

    def _format_date(self, date_str):
        if not date_str:
            return "N/A"
        try:
            return date_str.split('T')[0]
        except:
            return str(date_str)

    def _format_list(self, data_list, key=None):
        if not data_list:
            return "N/A"
        if key:
            return ", ".join([item.get(key, '未知') for item in data_list]) or "N/A"
        return ", ".join(data_list) or "N/A"
        
    def _format_item_details(self, item_data, item_type_override=None, indent_level=0):
        if not item_data:
            return "  " * indent_level + "错误: 传入的 item_data 为空。"

        details = []
        indent_str = "  " * indent_level # 缩进字符串
        
        item_type = item_type_override or item_data.get('Type', '未知类型')
        name = item_data.get('Name', '未知名称')
        emby_id = item_data.get('Id', 'N/A')
        path = item_data.get('Path', 'N/A')
        overview = item_data.get('Overview', 'N/A')
        provider_ids = item_data.get('ProviderIds', {})
        tmdb_id_val = provider_ids.get('Tmdb', 'N/A')
        imdb_id_val = provider_ids.get('Imdb', 'N/A')
        tvdb_id_val = provider_ids.get('Tvdb', 'N/A')
        
        user_data = item_data.get('UserData', {})
        played = user_data.get('Played', False)
        play_count = user_data.get('PlayCount', 0)
        is_favorite = user_data.get('IsFavorite', False)

        details.append(f"{indent_str}--- {item_type} 详细信息 ---")
        details.append(f"{indent_str}名称: {name}")
        details.append(f"{indent_str}Emby ID: {emby_id}")
        details.append(f"{indent_str}类型: {item_type}")
        
        if item_type in ["Movie", "Series", "Episode"]:
            details.append(f"{indent_str}TMDB ID: {tmdb_id_val}")
            details.append(f"{indent_str}IMDB ID: {imdb_id_val}")
            if item_type in ["Series", "Episode"]:
                 details.append(f"{indent_str}TVDB ID: {tvdb_id_val}")
        
        details.append(f"{indent_str}路径: {path}")

        if item_type in ["Movie", "Series", "Season", "Episode"]:
            overview_text = overview or 'N/A'
            # 正确处理简介的多行缩进
            formatted_overview = overview_text.replace('\n', '\n' + indent_str + '  ')
            details.append(f"{indent_str}简介:\n{indent_str}  {formatted_overview}")
            details.append(f"{indent_str}年份: {item_data.get('ProductionYear', 'N/A')}")
            details.append(f"{indent_str}社区评分: {item_data.get('CommunityRating', 'N/A')}")
            details.append(f"{indent_str}官方评级: {item_data.get('OfficialRating', 'N/A')}")
            details.append(f"{indent_str}Genres: {self._format_list(item_data.get('Genres'))}")
        
        if item_type in ["Movie", "Series"]:
            details.append(f"{indent_str}工作室: {self._format_list(item_data.get('Studios'), 'Name')}")
            details.append(f"{indent_str}首播日期: {self._format_date(item_data.get('PremiereDate'))}")
            details.append(f"{indent_str}标语: {self._format_list(item_data.get('Taglines'))}")
        
        if item_type == "Movie":
            details.append(f"{indent_str}时长: {self._format_runtime(item_data.get('RunTimeTicks'))}")
        
        if item_type == "Series":
            details.append(f"{indent_str}状态: {item_data.get('Status', 'N/A')}")
            details.append(f"{indent_str}结束日期: {self._format_date(item_data.get('EndDate'))}")

        if item_type == "Season":
            details.append(f"{indent_str}季号: {item_data.get('IndexNumber', 'N/A')}")
            details.append(f"{indent_str}父ID (剧集): {item_data.get('ParentId', 'N/A')}")
            details.append(f"{indent_str}剧集名 (SeriesName): {item_data.get('SeriesName', 'N/A')}")

        if item_type == "Episode":
            details.append(f"{indent_str}集号: {item_data.get('IndexNumber', 'N/A')}")
            details.append(f"{indent_str}季号 (ParentIndexNumber): {item_data.get('ParentIndexNumber', 'N/A')}")
            details.append(f"{indent_str}首播日期: {self._format_date(item_data.get('PremiereDate'))}")
            details.append(f"{indent_str}时长: {self._format_runtime(item_data.get('RunTimeTicks'))}")
            details.append(f"{indent_str}父ID (季): {item_data.get('ParentId', 'N/A')}")
            details.append(f"{indent_str}剧集名 (SeriesName): {item_data.get('SeriesName', 'N/A')}")
            details.append(f"{indent_str}季名 (SeasonName): {item_data.get('SeasonName', 'N/A')}")

        details.append(f"{indent_str}用户数据:")
        details.append(f"{indent_str}  已观看: {played}")
        details.append(f"{indent_str}  播放次数: {play_count}")
        details.append(f"{indent_str}  喜爱: {is_favorite}")
        
        details.append(f"{indent_str}--- --- ---")
        return "\n".join(details)

    def _fetch_series_structure(self, series_emby_id, series_name):
        self.progress.emit(f"剧集详情: '{series_name}' (Emby ID: {series_emby_id})")

        season_params = {
            'api_key': self.api_key,
            'ParentId': series_emby_id,
            'IncludeItemTypes': 'Season',
            'Fields': 'Name,Id,IndexNumber,Type,ParentId,Path,Overview,ProductionYear,UserData,SeriesName',
            'Recursive': 'false'
        }
        try:
            self.progress.emit(f"  正在查询 '{series_name}' 的季信息 (最多等待45秒)...")
            response_seasons = self.session.get(self.search_url_base, headers=self._emby_headers(), params=season_params, timeout=45)
            response_seasons.raise_for_status()
            seasons_data = response_seasons.json().get('Items', [])

            if not seasons_data:
                self.progress.emit(f"  未找到剧集 '{series_name}' (ID: {series_emby_id}) 下的任何季。")
                return

            seasons_data.sort(key=lambda s: s.get('IndexNumber', float('inf')))

            for season_item in seasons_data:
                self.progress.emit(self._format_item_details(season_item, item_type_override="Season", indent_level=1))
                if self.show_raw_json:
                    self.progress.emit(f"--- 季原始数据 (Emby ID: {season_item.get('Id')}) ---\n{json.dumps(season_item, indent=2, ensure_ascii=False)}\n--- --- ---")
                
                season_id = season_item.get('Id')
                season_display_name = season_item.get('Name') or f"第 {season_item.get('IndexNumber', '未知')} 季"

                episode_params = {
                    'api_key': self.api_key,
                    'ParentId': season_id,
                    'IncludeItemTypes': 'Episode',
                    'Fields': 'Name,Id,IndexNumber,Type,ParentId,SeasonName,SeriesName,Path,PremiereDate,Overview,RunTimeTicks,CommunityRating,ProviderIds,ParentIndexNumber,UserData',
                    'Recursive': 'false'
                }
                try:
                    self.progress.emit(f"    正在查询 '{season_display_name}' 的集信息 (最多等待90秒)...")
                    response_episodes = self.session.get(self.search_url_base, headers=self._emby_headers(), params=episode_params, timeout=90)
                    response_episodes.raise_for_status()
                    episodes_data = response_episodes.json().get('Items', [])

                    if not episodes_data:
                        self.progress.emit(f"    未找到季 '{season_display_name}' (ID: {season_id}) 下的任何集。")
                        continue
                    
                    episodes_data.sort(key=lambda e: e.get('IndexNumber', float('inf')))

                    for episode_item in episodes_data:
                        self.progress.emit(self._format_item_details(episode_item, item_type_override="Episode", indent_level=2))
                        if self.show_raw_json:
                            self.progress.emit(f"--- 集原始数据 (Emby ID: {episode_item.get('Id')}) ---\n{json.dumps(episode_item, indent=2, ensure_ascii=False)}\n--- --- ---")

                except requests.exceptions.RequestException as e:
                    self.error.emit(f"    错误: 查询季 '{season_display_name}' (ID: {season_id}) 的集信息时发生网络错误: {e}")
                except json.JSONDecodeError as e:
                    self.error.emit(f"    错误: 解析季 '{season_display_name}' (ID: {season_id}) 的集信息响应失败: {e}")
                except Exception as e:
                    self.error.emit(f"    错误: 处理季 '{season_display_name}' (ID: {season_id}) 的集信息时发生未知错误: {e}")

        except requests.exceptions.RequestException as e:
            self.error.emit(f"  错误: 查询剧集 '{series_name}' (ID: {series_emby_id}) 的季信息时发生网络错误: {e}")
        except json.JSONDecodeError as e:
            self.error.emit(f"  错误: 解析剧集 '{series_name}' (ID: {series_emby_id}) 的季信息响应失败: {e}")
        except Exception as e:
            self.error.emit(f"  错误: 处理剧集 '{series_name}' (ID: {series_emby_id}) 的季信息时发生未知错误: {e}")

    def run(self):
        if not all([self.server_url, self.api_key, self.tmdb_id_str]):
            self.error.emit("错误: 服务器地址、API Key 和 TMDB ID 不能为空。")
            self.finished.emit(); return
        
        if not self.search_movies and not self.search_series:
            self.error.emit("错误: 请至少选择一种媒体类型进行搜索 (电影或剧集)。")
            self.finished.emit(); return

        self.progress.emit(f"开始处理 TMDB ID: {self.tmdb_id_str}")

        include_item_types_list = []
        if self.search_movies: include_item_types_list.append("Movie")
        if self.search_series: include_item_types_list.append("Series")
        include_item_types_str = ",".join(include_item_types_list)

        base_search_params_fields = 'ProviderIds,Name,Type,Id,Path,Overview,ProductionYear,CommunityRating,ParentId,OfficialRating,Genres,Studios,PremiereDate,EndDate,Status,RunTimeTicks,Taglines,UserData'

        all_found_items_summary = []
        series_items_for_details = [] 
        detailed_series_ids = set() 

        # --- 阶段一：直接 TmdbId 参数搜索 ---
        try:
            self.progress.emit(f"\n--- 阶段一：尝试使用 'TmdbId={self.tmdb_id_str}' 参数直接搜索 (最多等待30秒) ---")
            direct_search_params = {
                'api_key': self.api_key,
                'Recursive': 'true', 
                'IncludeItemTypes': include_item_types_str,
                'Fields': base_search_params_fields,
                'TmdbId': self.tmdb_id_str 
            }
            
            response = self.session.get(self.search_url_base, headers=self._emby_headers(), params=direct_search_params, timeout=30)
            response.raise_for_status()
            
            direct_search_results_json = response.json()
            items_from_direct_search = direct_search_results_json.get('Items', [])

            if items_from_direct_search:
                self.progress.emit(f"直接 TmdbId 参数搜索成功，初步返回 {len(items_from_direct_search)} 个项目。正在筛选和格式化...")
                for item_data in items_from_direct_search:
                    p_ids = item_data.get('ProviderIds', {})
                    item_tmdb_id_val = str(p_ids.get('Tmdb', ''))
                    item_type = item_data.get('Type')
                    item_id = item_data.get('Id')
                    type_match = item_type in include_item_types_list

                    if item_tmdb_id_val == self.tmdb_id_str and type_match:
                        summary = f"  - 直接匹配: '{item_data.get('Name')}' (Emby ID: {item_id}, 类型: {item_type})"
                        if summary not in all_found_items_summary:
                             all_found_items_summary.append(summary)
                        
                        self.progress.emit(self._format_item_details(item_data))
                        if self.show_raw_json:
                            self.progress.emit(f"--- 项目原始数据 (直接搜索, Emby ID: {item_id}) ---\n{json.dumps(item_data, indent=2, ensure_ascii=False)}\n--- --- ---")
                        
                        if item_type == "Series" and self.search_series:
                            if item_id not in detailed_series_ids:
                                series_items_for_details.append(item_data)
                                detailed_series_ids.add(item_id)
            else:
                self.progress.emit("直接 TmdbId 参数搜索未返回任何项目。")
                if self.show_raw_json: 
                    self.progress.emit(f"服务器原始响应 (直接搜索): \n{json.dumps(direct_search_results_json, indent=2, ensure_ascii=False)}")

        except requests.exceptions.HTTPError as e:
            self.progress.emit(f"直接 TmdbId 参数搜索请求发生 HTTP 错误: {e.response.status_code if e.response else 'N/A'} - {e}")
            if e.response is not None and self.show_raw_json:
                try: self.progress.emit(f"响应内容: {json.dumps(e.response.json(), indent=2, ensure_ascii=False)}")
                except json.JSONDecodeError: self.progress.emit(f"响应内容 (非JSON): {e.response.text[:500]}")
        except requests.exceptions.RequestException as e:
            self.error.emit(f"错误: 直接 TmdbId 参数搜索时发生网络错误: {e}")
        except json.JSONDecodeError as e:
            self.error.emit(f"错误: 解析直接 TmdbId 搜索响应失败: {e}")
        except Exception as e:
            self.error.emit(f"错误: 处理直接 TmdbId 搜索结果时发生未知错误: {e}")

        # --- 阶段二：遍历 ProviderIds 搜索 (HasTmdbId=true) ---
        try:
            self.progress.emit(f"\n--- 阶段二：尝试使用 'HasTmdbId=true' 参数并遍历 ProviderIds 搜索 (最多等待120秒) ---")
            iter_search_params = {
                'api_key': self.api_key,
                'Recursive': 'true',
                'IncludeItemTypes': include_item_types_str,
                'Fields': base_search_params_fields,
                'HasTmdbId': 'true'
            }
            
            response = self.session.get(self.search_url_base, headers=self._emby_headers(), params=iter_search_params, timeout=120)
            response.raise_for_status()
            
            iter_search_results_json = response.json()
            all_items_with_tmdb = iter_search_results_json.get('Items', [])

            if all_items_with_tmdb:
                self.progress.emit(f"遍历 ProviderIds 搜索成功，共获取 {len(all_items_with_tmdb)} 个带 TMDB ID 的项目。正在筛选和格式化...")
                for item in all_items_with_tmdb:
                    provider_ids = item.get('ProviderIds', {})
                    item_tmdb_id_val = str(provider_ids.get('Tmdb', ''))
                    item_type = item.get('Type')
                    item_id = item.get('Id')
                    type_match = item_type in include_item_types_list
                    
                    if item_tmdb_id_val == self.tmdb_id_str and type_match:
                        summary = f"  - 遍历匹配: '{item.get('Name')}' (Emby ID: {item_id}, 类型: {item_type})"
                        if summary not in all_found_items_summary:
                            all_found_items_summary.append(summary)

                        self.progress.emit(self._format_item_details(item))
                        if self.show_raw_json:
                            self.progress.emit(f"--- 项目原始数据 (遍历搜索, Emby ID: {item_id}) ---\n{json.dumps(item, indent=2, ensure_ascii=False)}\n--- --- ---")
                        
                        if item_type == "Series" and self.search_series:
                            if item_id not in detailed_series_ids:
                                series_items_for_details.append(item)
                                detailed_series_ids.add(item_id)
            else:
                self.progress.emit("遍历 ProviderIds 搜索未返回任何带 TMDB ID 的项目。")
                if self.show_raw_json:
                    self.progress.emit(f"服务器原始响应 (遍历搜索): \n{json.dumps(iter_search_results_json, indent=2, ensure_ascii=False)}")

        except requests.exceptions.HTTPError as e:
            self.progress.emit(f"遍历 ProviderIds 搜索请求发生 HTTP 错误: {e.response.status_code if e.response else 'N/A'} - {e}")
            if e.response is not None and self.show_raw_json:
                try: self.progress.emit(f"响应内容: {json.dumps(e.response.json(), indent=2, ensure_ascii=False)}")
                except json.JSONDecodeError: self.progress.emit(f"响应内容 (非JSON): {e.response.text[:500]}")
        except requests.exceptions.RequestException as e:
            self.error.emit(f"错误: 遍历 ProviderIds 搜索时发生网络错误: {e}")
        except json.JSONDecodeError as e:
            self.error.emit(f"错误: 解析遍历 ProviderIds 搜索响应失败: {e}")
        except Exception as e:
            self.error.emit(f"错误: 处理遍历 ProviderIds 搜索结果时发生未知错误: {e}")

        if series_items_for_details:
            self.progress.emit(f"\n--- 开始获取所有匹配剧集的详细季/集结构 ({len(series_items_for_details)} 个剧集) ---")
            for series_to_detail in series_items_for_details:
                if series_to_detail.get("Type") == "Series":
                    self.progress.emit(f"\n正在为剧集 '{series_to_detail.get('Name')}' (Emby ID: {series_to_detail.get('Id')}) 获取详细结构...")
                    self._fetch_series_structure(series_to_detail.get('Id'), series_to_detail.get('Name'))
                else:
                    self.progress.emit(f"跳过获取 '{series_to_detail.get('Name')}' (ID: {series_to_detail.get('Id')}) 的详细结构，类型为 {series_to_detail.get('Type')}。")

        elif self.search_series and not any("类型: Series" in s for s in all_found_items_summary):
            self.progress.emit(f"\n在本次搜索中未找到与 TMDB ID '{self.tmdb_id_str}' 匹配的剧集项目以获取详细结构。")

        self.progress.emit("\n--- 搜索总结 ---")
        if not all_found_items_summary:
            self.progress.emit(f"未能在 Emby 中找到任何与 TMDB ID '{self.tmdb_id_str}' ({include_item_types_str}) 相关的项目。")
        else:
            self.progress.emit(f"已找到以下与 TMDB ID '{self.tmdb_id_str}' ({include_item_types_str}) 相关的顶级项目摘要:")
            unique_summaries = sorted(list(set(all_found_items_summary)))
            for item_summary in unique_summaries:
                 self.progress.emit(item_summary)
        self.progress.emit("--- 搜索操作结束 ---")
        self.finished.emit()

# --- QTextBrowser 日志处理器 ---
class QTextBrowserHandler(logging.Handler):
    def __init__(self, text_browser):
        super().__init__(); self.text_browser = text_browser
    def emit(self, record):
        msg = self.format(record)
        is_emby_searcher_info_error = (record.name == 'emby_searcher' and 
                                      record.levelno == logging.INFO and 
                                      ("错误:" in record.getMessage() or "Error:" in record.getMessage().capitalize()))
        is_emby_searcher_info_warning = (record.name == 'emby_searcher' and
                                         record.levelno == logging.INFO and
                                         ("警告:" in record.getMessage() or "Warning:" in record.getMessage().capitalize()))
        
        if record.levelno >= logging.ERROR or is_emby_searcher_info_error:
            msg = f'<font color="red">{msg}</font>'
        elif record.levelno == logging.WARNING or is_emby_searcher_info_warning:
            msg = f'<font color="orange">{msg}</font>'
        elif record.levelno == logging.INFO:
            blue_bold_keywords = [
                "---", "正在获取剧集", "剧集详情:", "正在为剧集", 
                "开始处理 TMDB ID:", "搜索总结", "搜索操作结束",
                "参数搜索成功", "遍历 ProviderIds 搜索成功"
            ]
            raw_msg_content = record.getMessage()
            if raw_msg_content.strip().startswith("---") or \
               any(kw in raw_msg_content for kw in blue_bold_keywords if not kw == "---" and not raw_msg_content.strip().startswith("--- " + kw)): # Avoid double styling for block titles like "--- Series 详细信息 ---"
                # Check if it's a block title like "--- Series 详细信息 ---" which is already handled by the _format_item_details
                # and should not be made bold again here if the title itself contains a keyword.
                is_block_title = raw_msg_content.strip().startswith("--- ") and raw_msg_content.strip().endswith(" ---")
                if not is_block_title or not any(kw in raw_msg_content for kw in ["详细信息","原始数据"]): # Style general keywords blue/bold
                     msg = f'<font color="blue"><b>{msg}</b></font>'
                elif is_block_title: # If it is a block title, keep it blue/bold (already handled or should be)
                     msg = f'<font color="blue"><b>{msg}</b></font>'


            elif "成功" in raw_msg_content and not raw_msg_content.strip().startswith("---"):
                 msg = f'<font color="green">{msg}</font>'

        self.text_browser.append(msg)

        raw_msg_content = record.getMessage()
        if raw_msg_content.strip().endswith("--- --- ---"):
             self.text_browser.append("") 

        self.text_browser.ensureCursorVisible()

# --- 主应用窗口 ---
class EmbySearcherApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Emby TMDB ID 搜索工具")
        self.setGeometry(200, 200, 850, 700)

        self.worker = None
        self.thread = None

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        form_layout = QGridLayout()
        form_layout.addWidget(QLabel("Emby 服务器地址:"), 0, 0); self.server_url_edit = QLineEdit(); self.server_url_edit.setPlaceholderText("例如: http://localhost:8096"); form_layout.addWidget(self.server_url_edit, 0, 1)
        form_layout.addWidget(QLabel("Emby API Key:"), 1, 0); self.api_key_edit = QLineEdit(); self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password); form_layout.addWidget(self.api_key_edit, 1, 1)

        config_buttons_layout = QHBoxLayout()
        self.save_config_button = QPushButton("保存配置"); self.save_config_button.clicked.connect(self.save_config)
        self.load_config_button = QPushButton("加载配置"); self.load_config_button.clicked.connect(self.load_config)
        config_buttons_layout.addWidget(self.load_config_button); config_buttons_layout.addWidget(self.save_config_button)
        form_layout.addLayout(config_buttons_layout, 2, 0, 1, 2)

        form_layout.addWidget(QLabel("TMDB ID:"), 3, 0); self.tmdb_id_edit = QLineEdit(); self.tmdb_id_edit.setPlaceholderText("电影或剧集的TMDB ID (纯数字)"); form_layout.addWidget(self.tmdb_id_edit, 3, 1)

        item_type_layout = QHBoxLayout()
        item_type_layout.addWidget(QLabel("搜索媒体类型:"))
        self.movie_checkbox = QCheckBox("电影"); self.movie_checkbox.setChecked(True)
        self.series_checkbox = QCheckBox("剧集"); self.series_checkbox.setChecked(True)
        item_type_layout.addWidget(self.movie_checkbox); item_type_layout.addWidget(self.series_checkbox); item_type_layout.addStretch()
        form_layout.addLayout(item_type_layout, 4, 0, 1, 2)

        self.show_raw_json_checkbox = QCheckBox("显示完整原始JSON数据")
        self.show_raw_json_checkbox.setChecked(False) 
        form_layout.addWidget(self.show_raw_json_checkbox, 5, 0, 1, 2)

        self.main_layout.addLayout(form_layout)

        self.search_button = QPushButton("搜索 Emby 项目") 
        self.search_button.clicked.connect(self.start_search)
        self.main_layout.addWidget(self.search_button)

        self.log_browser = QTextBrowser(); self.log_browser.setReadOnly(True); self.log_browser.setOpenExternalLinks(True)
        self.main_layout.addWidget(QLabel("日志输出:"))
        self.main_layout.addWidget(self.log_browser, 1)

        gui_handler = QTextBrowserHandler(self.log_browser); gui_handler.setFormatter(formatter)
        logging.getLogger('emby_searcher').addHandler(gui_handler)
        
        self.statusBar = self.statusBar(); self.statusBar.showMessage("准备就绪。")
        self.load_config()

        if not logging.getLogger('emby_searcher').hasHandlers():
             console_handler = logging.StreamHandler(sys.stdout)
             console_handler.setFormatter(formatter)
             logging.getLogger('emby_searcher').addHandler(console_handler)
        log.info("Emby TMDB ID 搜索工具已启动。")


    def save_config(self):
        config_data = {
            'server_url': self.server_url_edit.text(),
            'api_key': self.api_key_edit.text(),
            'search_movies': self.movie_checkbox.isChecked(),
            'search_series': self.series_checkbox.isChecked(),
            'show_raw_json': self.show_raw_json_checkbox.isChecked() 
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=4)
            log.info(f"配置已保存到 {CONFIG_FILE}"); self.statusBar.showMessage("配置已保存。", 3000)
        except IOError as e: log.error(f"保存配置失败: {e}"); QMessageBox.warning(self, "保存错误", f"无法保存配置: {e}")

    def load_config(self):
        default_url = 'http://localhost:8096'
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f: config_data = json.load(f)
                self.server_url_edit.setText(config_data.get('server_url', default_url))
                self.api_key_edit.setText(config_data.get('api_key', ''))
                self.movie_checkbox.setChecked(config_data.get('search_movies', True))
                self.series_checkbox.setChecked(config_data.get('search_series', True))
                self.show_raw_json_checkbox.setChecked(config_data.get('show_raw_json', False)) 
                log.info(f"配置已从 {CONFIG_FILE} 加载。"); self.statusBar.showMessage("配置已加载。", 3000)
            except (IOError, json.JSONDecodeError) as e:
                log.error(f"加载配置 '{CONFIG_FILE}' 失败: {e}. 使用默认值。")
                self.server_url_edit.setText(self.server_url_edit.text() or default_url)
                self.api_key_edit.setText(self.api_key_edit.text() or '')
                self.show_raw_json_checkbox.setChecked(False) 
        else:
            log.info(f"配置文件 {CONFIG_FILE} 未找到，使用默认值。")
            self.server_url_edit.setText(self.server_url_edit.text() or default_url)
            self.api_key_edit.setText(self.api_key_edit.text() or '')
            self.show_raw_json_checkbox.setChecked(False)


    def start_search(self):
        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "操作繁忙", "一个搜索操作已在进行中，请稍候。"); return

        server_url = self.server_url_edit.text(); api_key = self.api_key_edit.text(); tmdb_id = self.tmdb_id_edit.text()
        search_movies = self.movie_checkbox.isChecked(); search_series = self.series_checkbox.isChecked()
        show_raw_json = self.show_raw_json_checkbox.isChecked() 

        if not all([server_url, api_key, tmdb_id]):
            QMessageBox.critical(self, "输入错误", "请填写 Emby 服务器地址、API Key 和 TMDB ID。"); return
        if not (server_url.startswith("http://") or server_url.startswith("https://")):
             QMessageBox.critical(self, "输入错误", "Emby 服务器地址格式不正确 (应以 http:// 或 https:// 开头)。"); return
        if not search_movies and not search_series:
            QMessageBox.critical(self, "输入错误", "请至少选择一种媒体类型进行搜索 (电影或剧集)。"); return
        if not tmdb_id.isdigit():
            QMessageBox.critical(self, "输入错误", "TMDB ID 应为纯数字。"); return

        self.log_browser.clear()
        log.info("开始 TMDB ID 搜索操作...")
        self.statusBar.showMessage("正在搜索，请稍候..."); self.search_button.setEnabled(False)

        self.thread = QThread(self)
        self.worker = SearchWorker(server_url, api_key, tmdb_id, search_movies, search_series, show_raw_json)
        self.worker.moveToThread(self.thread)

        self.worker.progress.connect(log.info)
        self.worker.error.connect(log.error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self._on_search_finished)

        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def _on_search_finished(self):
        self.statusBar.showMessage("搜索操作完成。", 5000)
        self.search_button.setEnabled(True)
        self.thread = None
        self.worker = None

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            reply = QMessageBox.question(self,'确认退出',"搜索仍在进行中。确定退出？",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                event.ignore(); return
            else:
                log.info("正在尝试停止搜索线程...")
                self.thread.quit() 
                if not self.thread.wait(2000):
                    log.warning("搜索线程未能及时停止。应用将强制退出。")
                else:
                    log.info("搜索线程已停止。")
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = EmbySearcherApp()
    window.show()
    sys.exit(app.exec())

