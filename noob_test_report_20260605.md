======================================================================
  Noob Test 全量链接检查报告
======================================================================

部署信息：
  项目域名：https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com
  DEPLOY_ID：6b099ed3-7175-4a78-91f4-44570c84ed27
  检查时间：2026-06-05 17:41:49

SSL 证书：❌ 异常 - 

----------------------------------------------------------------------
链接检查统计：
  总 URL 数：1300
  ✅ 可达：735 (56.5%)
  ❌ 不可达：565
    - http_401：88
    - http_404：467
    - http_422：10

----------------------------------------------------------------------
### 部署问题（共 565 项）

  D1. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/_lookup/merchants
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cards_admin.py
  D2. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/accounts
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_merchant.py
  D3. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/accounts/user_id-test/staff
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_merchant.py
  D4. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/active-product-count
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D5. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/ai-prompts
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/glucose_v1.py
  D6. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/cos/config
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cos.py
  D7. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/cos/files
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cos.py
  D8. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/cos/migration/progress
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cos.py
  D9. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/cos/upload-limits
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cos.py
  D10. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/cos/usage
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cos.py
  D11. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/exchange-records
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points_exchange.py
  D12. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/knowledge-bases
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/knowledge.py
  D13. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/knowledge-bases/fallback-config
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/knowledge.py
  D14. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/knowledge-bases/import/task_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/knowledge.py
  D15. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/knowledge-bases/scene-bindings
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/knowledge.py
  D16. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/knowledge-bases/search-config
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/knowledge.py
  D17. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/knowledge-bases/stats/distribution
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/knowledge.py
  D18. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/knowledge-bases/stats/missed-questions
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/knowledge.py
  D19. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/knowledge-bases/stats/overview
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/knowledge.py
  D20. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/knowledge-bases/stats/top-hits
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/knowledge.py
  D21. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/knowledge-bases/stats/trend
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/knowledge.py
  D22. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/knowledge-bases/kb_id-test/entries
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/knowledge.py
  D23. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/map-config/copy-domain
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/maps.py
  D24. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/map-config/test-logs
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/maps.py
  D25. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin/maps/poi-search
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/maps.py
  D26. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-advice
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/glucose_v1.py
  D27. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-call/quota
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ai_call.py
  D28. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-call/settings
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_archive_optim_v1.py
  D29. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-call/settings/target_user_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_archive_optim_v1.py
  D30. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-config
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D31. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-config/active
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D32. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-config/sync-check
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D33. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-model-templates
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D34. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-model-templates/icons
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D35. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/alerts
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/glucose_v1.py
  D36. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/all/flat
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prompt_templates.py
  D37. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/allergies
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile.py
  D38. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/answers/answer_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/questionnaire.py
  D39. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/answers/answer_id-test/ai-status
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/questionnaire.py
  D40. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/answers/answer_id-test/follow-up
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/questionnaire.py
  D41. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/answers/answer_id-test/raw
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/questionnaire.py
  D42. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/answers/answer_id-test/report
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/questionnaire.py
  D43. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/abnormal-thresholds
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/admin_family_guardian.py
  D44. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/abnormal-thresholds/tid-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/admin_family_guardian.py
  D45. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/abnormal-thresholds/tid-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/admin_family_guardian.py
  D46. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/ai-home-config
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/ai_home_config.py
  D47. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/ai-home-config/upload-image
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/ai_home_config.py
  D48. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/ai-home-config/module-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/ai_home_config.py
  D49. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/alert-templates
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/admin_family_guardian.py
  D50. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/alert-templates/tid-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/admin_family_guardian.py
  D51. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/alert-templates/tid-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/admin_family_guardian.py
  D52. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/app-settings/chat-idle-timeout
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/app_settings.py
  D53. [http_422] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/config/login_ui_version
      诊断：HTTP 422错误
      修复：需要进一步诊断
      来源：backend/app/api/login_ui_config.py
  D54. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/feedback/feedback_id-test/status
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/feedback.py
  D55. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/merchant/accounts/user_id-test/reset-password
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/account_security.py
  D56. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/messages
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/admin_messages.py
  D57. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/password
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/account_security.py
  D58. [http_422] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/themes/theme_id-test
      诊断：HTTP 422错误
      修复：需要进一步诊断
      来源：backend/app/api/themes.py
  D59. [http_422] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/admin/themes/theme_id-test/activate
      诊断：HTTP 422错误
      修复：需要进一步诊断
      来源：backend/app/api/themes.py
  D60. [http_422] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/alert/click-tracking
      诊断：HTTP 422错误
      修复：需要进一步诊断
      来源：backend/app/api/family_guardian.py
  D61. [http_422] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/alert/event
      诊断：HTTP 422错误
      修复：需要进一步诊断
      来源：backend/app/api/family_guardian.py
  D62. [http_422] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/alert/verify
      诊断：HTTP 422错误
      修复：需要进一步诊断
      来源：backend/app/api/family_guardian.py
  D63. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/auth/force-change-password
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/account_security.py
  D64. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/care-card/contacts
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/care_card_v1.py
  D65. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/care-card/contacts/contact_id-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/care_card_v1.py
  D66. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/care-card/contacts/contact_id-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/care_card_v1.py
  D67. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/care-card/home-address
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/care_card_v1.py
  D68. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/care-card/share-location
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/care_card_v1.py
  D69. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/care-v1/user-preferences/ui-mode
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/ai_home_care_v1.py
  D70. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/care/alerts/_seed-demo
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/care_ai_home.py
  D71. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/care/alerts/alert_id-test/dismiss
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/care_ai_home.py
  D72. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/chat-sessions
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/chat_history.py
  D73. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/chat-sessions/batch-delete
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/chat_history.py
  D74. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/chat-sessions/clear-all
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/chat_history.py
  D75. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/chat-sessions/session_id-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/chat_history.py
  D76. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/chat-sessions/session_id-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/chat_history.py
  D77. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/chat-sessions/session_id-test/archive
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/chat_history.py
  D78. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/chat-sessions/session_id-test/pin
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/chat_history.py
  D79. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/chat-sessions/session_id-test/resume
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/chat_history.py
  D80. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/chat-sessions/session_id-test/share
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/chat_history.py
  D81. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/invitation
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family_management.py
  D82. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/invitation/code-test/accept
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family_management.py
  D83. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/invitation/code-test/reject
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family_management.py
  D84. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/management/management_id-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family_management.py
  D85. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/management/management_id-test/share-toggle
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family_management.py
  D86. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/member/admin/cleanup-orphan-invitations
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family_member_v2.py
  D87. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/member/member_id-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family_member_v2.py
  D88. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/member/member_id-test/invite
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family_member_v2.py
  D89. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/member/member_id-test/unbind
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family_member_v2.py
  D90. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/members
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family.py
  D91. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/members/member_id-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family.py
  D92. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/members/member_id-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family.py
  D93. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/family/sos
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family.py
  D94. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/feedback
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/feedback.py
  D95. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/guardian/v12/emergency/simulate-serial-call
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/guardian_system_v12.py
  D96. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/guardian/v12/managed/managed_user_id-test/proxy-pay
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/guardian_system_v12.py
  D97. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/guardian/v12/owner/direct-adjust
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/guardian_system_v12.py
  D98. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/guardian/v12/reminders
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/guardian_system_v12.py
  D99. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/guardian/v12/reminders/reminder_id-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/guardian_system_v12.py
  D100. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/guardian/v12/transfer/initiate
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/guardian_system_v12.py
  D101. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/guardian/v12/transfer/transfer_id-test/approve
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/guardian_system_v12.py
  D102. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/guardian/v12/transfer/transfer_id-test/cancel
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/guardian_system_v12.py
  D103. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/guardian/v12/transfer/transfer_id-test/reject
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/guardian_system_v12.py
  D104. [http_422] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health-alerts/check
      诊断：HTTP 422错误
      修复：需要进一步诊断
      来源：backend/app/api/health_dashboard.py
  D105. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health-reminders
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/health_dashboard.py
  D106. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health-reminders/reminder_id-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/health_dashboard.py
  D107. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/health-reminders/reminder_id-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/health_dashboard.py
  D108. [http_422] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/internal/checkup/parsed
      诊断：HTTP 422错误
      修复：需要进一步诊断
      来源：backend/app/api/family_guardian.py
  D109. [http_422] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/internal/user/registered
      诊断：HTTP 422错误
      修复：需要进一步诊断
      来源：backend/app/api/family_guardian.py
  D110. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/me/migrations/mig_id-test/confirm
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family_guardian.py
  D111. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/me/migrations/mig_id-test/reject
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/family_guardian.py
  D112. [http_422] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/auth/login
      诊断：HTTP 422错误
      修复：需要进一步诊断
      来源：backend/app/api/merchant_v1.py
  D113. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/bindding/wechat
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/wechat_bindding.py
  D114. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/bindding/wechat/qrcode
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/wechat_bindding.py
  D115. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/business-hours
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/order_enhancement.py
  D116. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/concurrency-limit
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/order_enhancement.py
  D117. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/password
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/account_security.py
  D118. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/shop/info
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/account_security.py
  D119. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/staff/create
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/account_security.py
  D120. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/staff/reset-password
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/account_security.py
  D121. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/staff/toggle-status
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/account_security.py
  D122. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/stores/store_id-test/booking-config
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/order_enhancement.py
  D123. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/v1/exports
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/merchant_v1.py
  D124. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/v1/invoice-profile
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/merchant_v1.py
  D125. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/v1/orders/order_item_id-test/attachments
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/merchant_v1.py
  D126. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/v1/orders/order_item_id-test/attachments/attachment_id-test
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/merchant_v1.py
  D127. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/v1/settlements/sid-test/confirm
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/merchant_v1.py
  D128. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/v1/settlements/sid-test/dispute
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/merchant_v1.py
  D129. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/v1/staff
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/merchant_v1.py
  D130. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/v1/staff/target_user_id-test/permissions
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/merchant_v1.py
  D131. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/merchant/v1/staff/target_user_id-test/status
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/merchant_v1.py
  D132. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/messages/read-all
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/messages.py
  D133. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/messages/message_id-test/read
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/messages.py
  D134. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/notifications/mark-read-by-order
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/order_enhancement.py
  D135. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/orders/attachment-meta
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/order_enhancement.py
  D136. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/tts/synthesize
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/tts.py
  D137. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/verifications/verify
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/member_qr.py
  D138. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/verify/checkin
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/member_qr.py
  D139. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/verify/member-qrcode
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/member_qr.py
  D140. [http_401] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/api/verify/redeem
      诊断：HTTP 401错误
      修复：需要进一步诊断
      来源：backend/app/api/member_qr.py
  D141. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/app/version-check
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/addresses_v2.py
  D142. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/appointments
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/medication_reminder.py
  D143. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/appointments/my
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/expert.py
  D144. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/archive
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/constitution.py
  D145. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/archive/diagnosis_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/constitution.py
  D146. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/article-categories
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_news.py
  D147. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/articles/article_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/content.py
  D148. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/asr-config
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_search.py
  D149. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/available
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons.py
  D150. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/available-methods
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/payment_methods.py
  D151. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/badge
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/medication_reminder.py
  D152. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/balance
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points.py
  D153. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/block-words
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_search.py
  D154. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/buttons/button_id-test/render-meta
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/questionnaire.py
  D155. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/by-id/template_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prompt_templates.py
  D156. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/by-product/product_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cards.py
  D157. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/calendar/cells
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D158. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/calendar/daily
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D159. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/calendar/daily-orders
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D160. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/calendar/items
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D161. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/calendar/kpi
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D162. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/calendar/list
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D163. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/calendar/monthly
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D164. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/calendar/views
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D165. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/care-partners
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D166. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/care/medication-ai-call
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D167. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/catalog
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/devices_v2.py
  D168. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/categories
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/products.py
  D169. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/categories-by-ids
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D170. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/category-product-count
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D171. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/category-tree
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D172. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/center
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/member_center_v2.py
  D173. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/challenges/mine
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/brain_game.py
  D174. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/challenges/challenge_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/brain_game.py
  D175. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkin-calendar
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D176. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkin-items
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D177. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkin-items/item_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D178. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkin-items/item_id-test/records
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D179. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkin-overview
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D180. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkin-records
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D181. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkin-statistics
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_health_plan.py
  D182. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkin-stats-summary
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D183. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkin/today-progress
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points.py
  D184. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkins
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/safety_rope_v1.py
  D185. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkout/info
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/h5_checkout.py
  D186. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkout/init
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/h5_checkout.py
  D187. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkup-details
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ocr_details.py
  D188. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkup-details/statistics
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ocr_details.py
  D189. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkup-details/detail_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ocr_details.py
  D190. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkup-reports
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile.py
  D191. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkup-reports/report_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile.py
  D192. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/comments
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/content.py
  D193. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/comparison/record_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report_history.py
  D194. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/config
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/email_notify.py
  D195. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/contacts
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/safety_rope_v1.py
  D196. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/contacts/check-phone
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/safety_rope_v1.py
  D197. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/content/articles
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D198. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/cos/upload-limits
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cos.py
  D199. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/counts
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/unified_orders.py
  D200. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/coupon/status
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/constitution.py
  D201. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/coupons
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D202. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/dashboard
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D203. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/dashboard/stats
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D204. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/dashboard/summary
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cards_admin_v2.py
  D205. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/dashboard/trend
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cards_admin_v2.py
  D206. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/day
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant_dashboard.py
  D207. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/device/list
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D208. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/diagnosis
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/tcm.py
  D209. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/diagnosis-by-answer/answer_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/constitution.py
  D210. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/diagnosis/diagnosis_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/tcm.py
  D211. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/digital-human/digital_human_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/function_button.py
  D212. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/disclaimers
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ai_center.py
  D213. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/disclaimers/chat_type-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ai_center.py
  D214. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/disease-presets
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D215. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/drug-details
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ocr_details.py
  D216. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/drug-details/statistics
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ocr_details.py
  D217. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/drug-details/detail_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ocr_details.py
  D218. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/drug-details/detail_id-test/conversation
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ocr_details.py
  D219. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/drug-keywords
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/search.py
  D220. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/encyclopedia/constitution_type-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/constitution.py
  D221. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/exchange-records
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points_exchange.py
  D222. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/exchange-records/record_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points_exchange.py
  D223. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/family-member/relation-options
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D224. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/family-members/guarded-flags
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_archive_optim_v1.py
  D225. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/family/invite-history
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/guardian_system_v13.py
  D226. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/family/list
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/guardian_system_v13.py
  D227. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/family/member/member_id-test/delete-preview
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/guardian_bugfix_v1.py
  D228. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/family/proxy-pay/detail
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/guardian_system_v13.py
  D229. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/favorites
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/content.py
  D230. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/font-setting
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/font_setting.py
  D231. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/function-buttons
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/function_button.py
  D232. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/guardian-count
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/reverse_guardian.py
  D233. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/guardian/summary
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_archive_optim_v1.py
  D234. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/guardian/managed_user_id-test/devices
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_archive_optim_v1.py
  D235. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/guide-status
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile.py
  D236. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/h5/bottom-nav
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/bottom_nav.py
  D237. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health-archive-v5/overview
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_archive_v5.py
  D238. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health-event/timeline
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D239. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health-info/profile_id-test/family-history
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D240. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health-info/profile_id-test/surgery-history
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D241. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health/users
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D242. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health/users/user_id-test/members
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D243. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/hero-counts
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_archive_optim_v2.py
  D244. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/history
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/search.py
  D245. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/home-banners
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/home_config.py
  D246. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/home-config
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/home_config.py
  D247. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/home-menus
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/home_config.py
  D248. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/hot
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/city.py
  D249. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/hot-recommendations
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/products.py
  D250. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/invite/invite_code-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/reverse_guardian.py
  D251. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/items
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/service.py
  D252. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/items/item_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/service.py
  D253. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/latest
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/glucose_v1.py
  D254. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/level
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points.py
  D255. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/list
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/city.py
  D256. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/locate
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/city.py
  D257. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/logs
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/email_notify.py
  D258. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/mall
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points.py
  D259. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/mall/items/item_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points_exchange.py
  D260. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/mall/products
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points.py
  D261. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/maps/geo-config
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/maps.py
  D262. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/maps/static-map
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/maps.py
  D263. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/me
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/auth.py
  D264. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/me/renewable
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cards_v2.py
  D265. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/me/stats
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/users.py
  D266. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/me/wallet
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cards.py
  D267. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/me/user_card_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cards.py
  D268. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/me/user_card_id-test/redemption-code/current
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cards_v2.py
  D269. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/me/user_card_id-test/usage-logs
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cards_v2.py
  D270. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medical-history
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile.py
  D271. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medical-record/list
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D272. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medical-record/record_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D273. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medication-ai-call
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D274. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medication-library/search
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D275. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medication-library/stats
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D276. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medication-library/drug_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D277. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medication-plans/hero-count
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/medication_plans_v1.py
  D278. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medication-plans/summary
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/medication_plans_v1.py
  D279. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medication-plans/today
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/medication_plans_v1.py
  D280. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medication-reminder/plans/plan_id-test/ai-call
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ai_call.py
  D281. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medication-stats/monthly-compliance
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/medication_plans_v1.py
  D282. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medications
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D283. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medications/check-batch
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D284. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medications/list
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D285. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medications/summary
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D286. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/medications/reminder_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D287. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/member/member_id-test/alert-history
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_archive_optim_v2.py
  D288. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/member/member_id-test/alert-settings
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_archive_optim_v2.py
  D289. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/member/member_id-test/devices
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_archive_optim_v2.py
  D290. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/member/member_id-test/reports
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report_interpret.py
  D291. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/members
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_archive_optim_v2.py
  D292. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/merchant-profile
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/auth.py
  D293. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/meta
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_metric_card_v1.py
  D294. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/mine
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons.py
  D295. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/mode-preference
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/user_mode_preference.py
  D296. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/month
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant_dashboard.py
  D297. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/month-day
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant_dashboard.py
  D298. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/my
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/devices_v2.py
  D299. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/my-guardians
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/reverse_guardian.py
  D300. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/news/tags/suggest
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_news.py
  D301. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/notices/active
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/notice.py
  D302. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/offline-reason-options
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D303. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D304. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders/distribution
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D305. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders/records
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D306. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders/statistics
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D307. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders/trends
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D308. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders/unified
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D309. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders/unified/order_id-test/refund-detail
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D310. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders/v2/enums
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D311. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders/v2/stats
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D312. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders/verify-code/code-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D313. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders/order_id-test/attachments
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D314. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders/order_id-test/detail
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D315. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/orders/order_id-test/notes
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant.py
  D316. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/placeholder-catalog
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/questionnaire.py
  D317. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/plans
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/medication_reminder.py
  D318. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/plans/exists
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/medication_today_v1.py
  D319. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/points/coupons/coupon_id-test/stock-info
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points_admin.py
  D320. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/points/levels
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D321. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/points/mall/item_id-test/change-logs
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points_admin.py
  D322. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/points/rules
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D323. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-picker
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D324. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/products/categories
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D325. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/products/services
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points_admin.py
  D326. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/products/product_id-test/detail
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D327. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/products/product_id-test/form-fields
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D328. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/products/product_id-test/skus
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D329. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/products/product_id-test/stores
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D330. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/profile
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile.py
  D331. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/profile/member/member_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile.py
  D332. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/prompts
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ai_center.py
  D333. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/prompts/chat_type-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ai_center.py
  D334. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/questions
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/tcm.py
  D335. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/quota-usage
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/member_center_v2.py
  D336. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/rankings
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/brain_game.py
  D337. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/recommend-words
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_search.py
  D338. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/recommended-plans
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_health_plan.py
  D339. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/recommended-plans/plan_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D340. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/recommended-plans/plan_id-test/tasks
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_health_plan.py
  D341. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/records
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/glucose_v1.py
  D342. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/redeem-code-batches
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D343. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/redeem-code-batches/batch_id-test/codes
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D344. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/redeem-code-batches/batch_id-test/codes/export
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D345. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/redeem-codes/code-test/status
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/third_party_openapi.py
  D346. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/referral/stats
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D347. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/refresh-config
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ai_home_optim_v4.py
  D348. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/regions
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/addresses_v2.py
  D349. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/regions/tree
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/brain_game.py
  D350. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/register-settings
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/auth.py
  D351. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/relation-types
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D352. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/reminder
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/glucose_v1.py
  D353. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/reminder-setting
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D354. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/report
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/glucose_v1.py
  D355. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/report/alerts
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report.py
  D356. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/report/detail/report_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report.py
  D357. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/report/interpret/detail/report_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report_interpret.py
  D358. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/report/interpret/session/session_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report_interpret.py
  D359. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/report/interpret/session/session_id-test/messages
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report_interpret.py
  D360. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/report/interpret/session/session_id-test/ocr-detail
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report_interpret.py
  D361. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/report/interpret/session/session_id-test/stream
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report_interpret.py
  D362. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/report/interpret/session/session_id-test/task-status
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report_interpret.py
  D363. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/report/list
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report.py
  D364. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/report/share/token-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report.py
  D365. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/report/trend/indicator_name-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report.py
  D366. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/reports/report_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/checkup_api_v2.py
  D367. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/result/diagnosis_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/constitution.py
  D368. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/sandbox-confirm
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/unified_orders.py
  D369. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/scope-limits
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D370. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/sdk
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_sdk_health.py
  D371. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/seed-packs
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/seed_import.py
  D372. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/seed-packs/code-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/seed_import.py
  D373. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/self
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile_self.py
  D374. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/sensitive-words
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/ai_center.py
  D375. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/server-time
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/system.py
  D376. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/services/categories
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D377. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/services/items
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D378. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/session-context
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/auth.py
  D379. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/sessions
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/chat.py
  D380. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/sessions/session_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/chat.py
  D381. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/sessions/session_id-test/first-message-stream
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/chat.py
  D382. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/sessions/session_id-test/messages
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/chat.py
  D383. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/settings/protocol
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D384. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/settings/register
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D385. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/settings/reminder-advance
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D386. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/settings/timeout-policy
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D387. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/share/share_token-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/chat_share.py
  D388. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/share/token-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/drug_identify_share.py
  D389. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/shared/share_token-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report_history.py
  D390. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/skus/sku_id-test/used
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D391. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/slot/target_date-test/slot_no-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant_dashboard.py
  D392. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/slots
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/h5_checkout.py
  D393. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/statistics
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_search.py
  D394. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/statistics/refund-reasons
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D395. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/statistics/sales
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D396. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/statistics/trends
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D397. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/stats
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/glucose_v1.py
  D398. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/status
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/favorites.py
  D399. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/store-bindding/products
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D400. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/store-bindding/products/product_id-test/bound-count
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D401. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/store-bindding/products/product_id-test/stores
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D402. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/store-bindding/stores
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D403. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/store-bindding/stores/store_id-test/products
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D404. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/stores
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_merchant.py
  D405. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/stores/recommend
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D406. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/stores/store_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_merchant.py
  D407. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/suggest
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/medication_add_optim_v1.py
  D408. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/summary
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons.py
  D409. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/summary-stats/profile_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D410. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/summary/profile_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prd469_health_v5.py
  D411. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/symptom-tags
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/product_admin.py
  D412. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/system-config/doctor-consult
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/medication_library_v3.py
  D413. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/system/configs
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D414. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/tasks
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/points.py
  D415. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/template-categories
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_health_plan.py
  D416. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/template-categories/category_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D417. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/templates
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/questionnaire.py
  D418. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/templates/by-code/code-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/questionnaire.py
  D419. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/templates/template_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/questionnaire.py
  D420. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/time-slots
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/common.py
  D421. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/today
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/medication_reminder.py
  D422. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/today-todos
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D423. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/type-descriptions
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D424. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/unread-count
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/notifications_unified.py
  D425. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/usable-for-order
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons.py
  D426. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/user-checkin-details
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_health_plan.py
  D427. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/user-checkin-plans
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_health_plan.py
  D428. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/user-daily-summary
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin_health_plan.py
  D429. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/user-info
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/brain_game.py
  D430. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/user-plans
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D431. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/user-plans/plan_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_plan_v2.py
  D432. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/user/addresses
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/addresses_v2.py
  D433. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/users
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/admin.py
  D434. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/validity-options
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D435. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/verify-code/code-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/order.py
  D436. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/visits
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile.py
  D437. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/voice-service/vad-config
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/function_button.py
  D438. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/wechat-config
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/brain_game.py
  D439. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/week
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/merchant_dashboard.py
  D440. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/card_def_id-test/usage-logs
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cards_admin_v2.py
  D441. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/card_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/cards.py
  D442. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/channel_code-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/payment_config.py
  D443. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/channel_code-test/default-notify-url
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/payment_config.py
  D444. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/config_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prompt_type_config.py
  D445. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/consultant_id-test/medications
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/consultant_profile_card.py
  D446. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/consultant_id-test/profile_card
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/consultant_profile_card.py
  D447. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/coupon_id-test/grants
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D448. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/coupon_id-test/grants/export
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/coupons_admin.py
  D449. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/expert_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/expert.py
  D450. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/expert_id-test/schedules
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/expert.py
  D451. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/form_id-test/fields
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/appointment_form_admin.py
  D452. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/order_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/order.py
  D453. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/plan_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/plan.py
  D454. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/plan_id-test/tasks
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/plan.py
  D455. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/products.py
  D456. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product_id-test/available-stores
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/products.py
  D457. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product_id-test/related
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/products.py
  D458. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product_id-test/time-slots/availability
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/products.py
  D459. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/profile_id-test/events
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile_v3.py
  D460. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/profile_id-test/medication-plan
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile_v3.py
  D461. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/profile_id-test/metric/metric_type-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile_v3.py
  D462. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/profile_id-test/today-metrics
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_profile_v3.py
  D463. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/profile_id-test/metric_type-test/history
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_metric_card_v1.py
  D464. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/profile_id-test/metric_type-test/record_id-test/can-delete
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/health_metric_card_v1.py
  D465. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/prompt_type-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/prompt_templates.py
  D466. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/record_id-test
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/report_history.py
  D467. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/store_id-test/contact
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/stores_public.py
  D468. [404_api_route] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/tag_id-test/goods
      诊断：API路由未匹配到 gateway 或未正确注册
      修复：检查 gateway conf.d 配置中的 location 块
      来源：backend/app/api/tag_recommend.py
  D469. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/abnormal-thresholds
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/abnormal-thresholds/page.tsx
  D470. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/admin-settlements
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/admin-settlements/page.tsx
  D471. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-call-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/ai-call-config/page.tsx
  D472. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-center/disclaimers
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/ai-center/disclaimers/page.tsx
  D473. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-center/prompts
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/ai-center/prompts/page.tsx
  D474. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-center/sensitive-words
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/ai-center/sensitive-words/page.tsx
  D475. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/ai-config/page.tsx
  D476. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-config/chat-timeout
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/ai-config/chat-timeout/page.tsx
  D477. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ai-config/video-consult
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/ai-config/video-consult/page.tsx
  D478. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/alert-logs
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/alert-logs/page.tsx
  D479. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/alert-templates
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/alert-templates/page.tsx
  D480. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/audit/center
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/audit/center/page.tsx
  D481. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/audit/phones
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/audit/phones/page.tsx
  D482. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/bottom-nav
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/bottom-nav/page.tsx
  D483. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/chat-records
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/chat-records/page.tsx
  D484. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/chat-records/id-test
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/chat-records/[id]/page.tsx
  D485. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/checkup-details
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/checkup-details/page.tsx
  D486. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/city-management
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/city-management/page.tsx
  D487. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/constitution-content
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/constitution-content/page.tsx
  D488. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/content/articles
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/content/articles/page.tsx
  D489. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/content/categories
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/content/categories/page.tsx
  D490. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/content/news
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/content/news/page.tsx
  D491. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/cos-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/cos-config/page.tsx
  D492. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/dashboard
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/dashboard/page.tsx
  D493. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/digital-humans
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/digital-humans/page.tsx
  D494. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/disease-presets
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/disease-presets/page.tsx
  D495. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/drug-details
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/drug-details/page.tsx
  D496. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/email-notify
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/email-notify/page.tsx
  D497. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/emergency-sources
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/emergency-sources/page.tsx
  D498. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/fallback-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/fallback-config/page.tsx
  D499. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/family-management
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/family-management/page.tsx
  D500. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/function-buttons
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/function-buttons/page.tsx
  D501. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/guardian-relations
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/guardian-relations/page.tsx
  D502. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health-plan/categories
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/health-plan/categories/page.tsx
  D503. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health-plan/recommended
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/health-plan/recommended/page.tsx
  D504. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health-plan/recommended/planId-test/tasks
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/health-plan/recommended/[planId]/tasks/page.tsx
  D505. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health-records
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/health-records/page.tsx
  D506. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/health-records/statistics
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/health-records/statistics/page.tsx
  D507. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/home-banners
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/home-banners/page.tsx
  D508. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/home-settings
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/home-settings/page.tsx
  D509. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/home-settings/ai-home-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/home-settings/ai-home-config/page.tsx
  D510. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/home-settings/ai-home-config/logs
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/home-settings/ai-home-config/logs/page.tsx
  D511. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/knowledge
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/knowledge/page.tsx
  D512. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/knowledge/id-test
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/knowledge/[id]/page.tsx
  D513. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/knowledge/stats
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/knowledge/stats/page.tsx
  D514. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/map-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/map-config/page.tsx
  D515. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/membership/free-quota
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/membership/free-quota/page.tsx
  D516. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/membership/plans
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/membership/plans/page.tsx
  D517. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/merchant-categories
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/merchant-categories/page.tsx
  D518. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/merchant/accounts
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/merchant/accounts/page.tsx
  D519. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/merchant/business-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/merchant/business-config/page.tsx
  D520. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/merchant/stores
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/merchant/stores/page.tsx
  D521. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/merchant/stores/id-test/business-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/merchant/stores/[id]/business-config/page.tsx
  D522. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/notices
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/notices/page.tsx
  D523. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ocr-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/ocr-config/page.tsx
  D524. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/ocr-global-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/ocr-global-config/page.tsx
  D525. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/payment-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/payment-config/page.tsx
  D526. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/points/levels
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/points/levels/page.tsx
  D527. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/points/rules
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/points/rules/page.tsx
  D528. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/appointment-forms
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/appointment-forms/page.tsx
  D529. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/cards
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/cards/page.tsx
  D530. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/cards/dashboard
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/cards/dashboard/page.tsx
  D531. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/categories
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/categories/page.tsx
  D532. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/coupons
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/coupons/page.tsx
  D533. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/new-user-coupons
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/new-user-coupons/page.tsx
  D534. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/orders
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/orders/page.tsx
  D535. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/orders/dashboard
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/orders/dashboard/page.tsx
  D536. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/partners
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/partners/page.tsx
  D537. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/products
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/products/page.tsx
  D538. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/redemptions
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/redemptions/page.tsx
  D539. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/statistics
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/statistics/page.tsx
  D540. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/store-bindding
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/store-bindding/page.tsx
  D541. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/tags
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/tags/page.tsx
  D542. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/product-system/visits
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/product-system/visits/page.tsx
  D543. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/profile
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/profile/page.tsx
  D544. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/profile/change-password
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/profile/change-password/page.tsx
  D545. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/prompt-templates
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/prompt-templates/page.tsx
  D546. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/questionnaire-templates
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/questionnaire-templates/page.tsx
  D547. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/referral
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/referral/page.tsx
  D548. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/relation-types
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/relation-types/page.tsx
  D549. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/search-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/search-config/page.tsx
  D550. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/search/asr-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/search/asr-config/page.tsx
  D551. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/search/block-words
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/search/block-words/page.tsx
  D552. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/search/recommend
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/search/recommend/page.tsx
  D553. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/search/statistics
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/search/statistics/page.tsx
  D554. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/share-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/share-config/page.tsx
  D555. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/sms
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/sms/page.tsx
  D556. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/system-messages
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/system-messages/page.tsx
  D557. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/system-messages/send
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/system-messages/send/page.tsx
  D558. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/system/sdk-health
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/system/sdk-health/page.tsx
  D559. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/system/seed-import
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/system/seed-import/page.tsx
  D560. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/tcm-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/tcm-config/page.tsx
  D561. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/theme-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/theme-config/page.tsx
  D562. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/tts-config
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/tts-config/page.tsx
  D563. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/users
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/users/page.tsx
  D564. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/voice-service
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/voice-service/page.tsx
  D565. [404_missing_spa_fallback] https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com/wechat-push
      诊断：前端页面返回404，缺少 SPA fallback 配置
      修复：检查前端 web 服务器 (nginx) 配置，确保所有路由回退到 index.html
      来源：admin-web/src/app/(admin)/wechat-push/page.tsx

======================================================================