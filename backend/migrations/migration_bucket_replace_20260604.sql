-- ============================================================
-- Bucket 路径批量替换迁移脚本
-- 日期：2026-06-04
-- 说明：将数据库中所有存量的旧 Bucket 名称替换为新 Bucket 名称
--   旧：xiaokang-1323135906
--   新：xiaokang-prod-1420478721
-- 策略：全库扫描所有 VARCHAR/TEXT/JSON 字段，自动识别并替换
-- 注意：此脚本仅修改数据库中的 URL 文本，不涉及 COS 文件实际迁移
-- ============================================================

-- 使用目标数据库
USE bini_health;

-- ============================================================
-- 第一步：执行前快照（记录受影响行数，便于回滚参考）
-- ============================================================

-- 输出当前时间
SELECT CONCAT('迁移开始时间: ', NOW()) AS migration_start;

-- ============================================================
-- 第二步：生成全库扫描存储过程
-- 该存储过程自动遍历所有表的所有字符串/文本/JSON字段，
-- 查找包含旧 Bucket 名称的值并执行 REPLACE
-- ============================================================

DROP PROCEDURE IF EXISTS sp_replace_bucket_name;

DELIMITER $$

CREATE PROCEDURE sp_replace_bucket_name()
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE tbl_name VARCHAR(128);
    DECLARE col_name VARCHAR(128);
    DECLARE col_type VARCHAR(64);
    DECLARE affected_rows INT DEFAULT 0;
    DECLARE total_affected INT DEFAULT 0;
    DECLARE sql_stmt TEXT;
    DECLARE old_bucket VARCHAR(200) DEFAULT 'xiaokang-1323135906';
    DECLARE new_bucket VARCHAR(200) DEFAULT 'xiaokang-prod-1420478721';

    -- 游标：遍历当前库中所有表的字符串类型字段
    -- 注意：cos_configs.bucket 是系统配置值，必须排除，不可被替换
    DECLARE col_cursor CURSOR FOR
        SELECT
            t.TABLE_NAME,
            c.COLUMN_NAME,
            c.DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS c
        JOIN INFORMATION_SCHEMA.TABLES t
            ON c.TABLE_NAME = t.TABLE_NAME
            AND c.TABLE_SCHEMA = t.TABLE_SCHEMA
        WHERE c.TABLE_SCHEMA = DATABASE()
            AND t.TABLE_TYPE = 'BASE TABLE'
            AND c.DATA_TYPE IN (
                'varchar', 'char', 'text', 'tinytext',
                'mediumtext', 'longtext', 'json'
            )
            AND NOT (c.TABLE_NAME = 'cos_configs' AND c.COLUMN_NAME = 'bucket')
        ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    -- 创建日志表（如果不存在）
    CREATE TABLE IF NOT EXISTS _migration_bucket_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        table_name VARCHAR(128) NOT NULL,
        column_name VARCHAR(128) NOT NULL,
        affected_rows INT DEFAULT 0,
        executed_at DATETIME DEFAULT NOW()
    );

    OPEN col_cursor;

    read_loop: LOOP
        FETCH col_cursor INTO tbl_name, col_name, col_type;
        IF done THEN
            LEAVE read_loop;
        END IF;

        -- 跳过日志表及其他迁移辅助表
        IF tbl_name LIKE '_migration%' THEN
            ITERATE read_loop;
        END IF;

        -- 构造 UPDATE 语句
        -- 对 JSON 类型字段使用 JSON_REPLACE 逻辑较复杂且 MySQL 5.7 支持有限，
        -- 这里对 JSON 字段也使用 REPLACE 函数（MySQL 会自动处理字符串转换）
        SET @sql_stmt = CONCAT(
            'UPDATE `', tbl_name, '`',
            ' SET `', col_name, '` = REPLACE(`', col_name, '`, ''', old_bucket, ''', ''', new_bucket, ''')',
            ' WHERE `', col_name, '` LIKE ''%', old_bucket, '%'''
        );

        -- 准备并执行
        SET @exec_sql = @sql_stmt;
        PREPARE stmt FROM @exec_sql;
        EXECUTE stmt;
        SET affected_rows = ROW_COUNT();
        DEALLOCATE PREPARE stmt;

        -- 记录日志
        IF affected_rows > 0 THEN
            INSERT INTO _migration_bucket_log (table_name, column_name, affected_rows)
            VALUES (tbl_name, col_name, affected_rows);
            SET total_affected = total_affected + affected_rows;
        END IF;

    END LOOP;

    CLOSE col_cursor;

    -- 输出汇总
    SELECT CONCAT('迁移完成，总计更新 ', total_affected, ' 条记录') AS summary;

END$$

DELIMITER ;

-- ============================================================
-- 第三步：执行迁移
-- ============================================================

CALL sp_replace_bucket_name();

-- ============================================================
-- 第四步：查看迁移结果
-- ============================================================

SELECT
    table_name AS '表名',
    column_name AS '字段名',
    affected_rows AS '更新行数',
    executed_at AS '执行时间'
FROM _migration_bucket_log
ORDER BY affected_rows DESC, table_name, column_name;

-- ============================================================
-- 第五步：验证 —— 全库扫描检查是否还有遗漏的旧 Bucket 引用
-- ============================================================

SELECT CONCAT('验证开始时间: ', NOW()) AS verify_start;

-- 创建验证存储过程：遍历所有字符串字段，报告仍有旧 Bucket 的记录
DROP PROCEDURE IF EXISTS sp_verify_bucket_replace;

DELIMITER $$

CREATE PROCEDURE sp_verify_bucket_replace()
BEGIN
    DECLARE done INT DEFAULT FALSE;
    DECLARE tbl_name VARCHAR(128);
    DECLARE col_name VARCHAR(128);
    DECLARE remaining_count INT DEFAULT 0;
    DECLARE total_remaining INT DEFAULT 0;

    DECLARE verify_cursor CURSOR FOR
        SELECT TABLE_NAME, COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
            AND DATA_TYPE IN ('varchar', 'char', 'text', 'tinytext', 'mediumtext', 'longtext', 'json')
        ORDER BY TABLE_NAME, ORDINAL_POSITION;

    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = TRUE;

    OPEN verify_cursor;

    verify_loop: LOOP
        FETCH verify_cursor INTO tbl_name, col_name;
        IF done THEN
            LEAVE verify_loop;
        END IF;

        -- 跳过日志表
        IF tbl_name LIKE '_migration%' THEN
            ITERATE verify_loop;
        END IF;

        -- 构造 COUNT 查询
        SET @count_sql = CONCAT(
            'SELECT COUNT(*) INTO @cnt FROM `', tbl_name, '`',
            ' WHERE `', col_name, '` LIKE ''%xiaokang-1323135906%'''
        );
        PREPARE count_stmt FROM @count_sql;
        EXECUTE count_stmt;
        DEALLOCATE PREPARE count_stmt;

        IF @cnt > 0 THEN
            SELECT CONCAT('[警告] ', tbl_name, '.', col_name, ': 仍有 ', @cnt, ' 条未替换') AS warning;
            SET total_remaining = total_remaining + @cnt;
        END IF;
    END LOOP;

    CLOSE verify_cursor;

    IF total_remaining = 0 THEN
        SELECT '验证通过：数据库中已无旧 Bucket 引用。' AS verify_result;
    ELSE
        SELECT CONCAT('警告：仍有 ', total_remaining, ' 条记录未替换，请检查！') AS verify_result;
    END IF;
END$$

DELIMITER ;

CALL sp_verify_bucket_replace();

-- 验证 cos_configs 表（bucket 字段本身不应被替换，它是配置值！）
SELECT
    id,
    bucket,
    'cos_configs.bucket 是配置字段，不应被替换' AS note
FROM cos_configs
WHERE bucket LIKE '%xiaokang%';

DROP PROCEDURE IF EXISTS sp_verify_bucket_replace;

-- ============================================================
-- 第六步：清理
-- ============================================================

DROP PROCEDURE IF EXISTS sp_replace_bucket_name;

-- 日志表保留，供人工核查后手动删除：
-- DROP TABLE IF EXISTS _migration_bucket_log;

SELECT CONCAT('迁移脚本执行完毕，时间: ', NOW()) AS migration_end;

-- ============================================================
-- 附录：手动回滚参考
-- 如果需要回滚，请执行以下步骤：
-- 1. 查看日志表: SELECT * FROM _migration_bucket_log;
-- 2. 将下方 SQL 中的新/旧 Bucket 名称互换后重新执行存储过程
--    或者使用备份恢复数据
-- 回滚 SQL 参考：
--   UPDATE 表名 SET 字段名 = REPLACE(字段名, 'xiaokang-prod-1420478721', 'xiaokang-1323135906')
--   WHERE 字段名 LIKE '%xiaokang-prod-1420478721%';
-- ============================================================
