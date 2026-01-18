-- Seed Impact Previews for Payroll Runs
-- This script generates impact preview records for all payroll runs

-- First, let's get a list of all payroll runs and create impact previews

DO $$
DECLARE
    rec RECORD;
    prev_rec RECORD;
    prev_id UUID;
    prev_gross NUMERIC(18,2);
    prev_net NUMERIC(18,2);
    prev_paye NUMERIC(18,2);
    prev_emp_cost NUMERIC(18,2);
    prev_emp_count INTEGER;
    curr_emp_cost NUMERIC(18,2);
    g_variance NUMERIC(18,2);
    n_variance NUMERIC(18,2);
    p_variance NUMERIC(18,2);
    e_variance NUMERIC(18,2);
    g_variance_pct NUMERIC(5,2);
    summary TEXT;
BEGIN
    -- Iterate through payroll runs ordered by entity and period
    FOR rec IN 
        SELECT id, name, entity_id, period_start, period_end, status,
               COALESCE(total_gross_pay, 0) as total_gross_pay,
               COALESCE(total_net_pay, 0) as total_net_pay,
               COALESCE(total_paye, 0) as total_paye,
               COALESCE(total_pension_employer, 0) as total_pension_employer,
               COALESCE(total_nsitf, 0) as total_nsitf,
               COALESCE(total_itf, 0) as total_itf,
               COALESCE(total_employees, 0) as total_employees
        FROM payroll_runs
        WHERE status IN ('APPROVED', 'PROCESSING', 'COMPLETED', 'PAID')
        ORDER BY entity_id, period_start
    LOOP
        -- Check if impact preview already exists
        IF EXISTS (SELECT 1 FROM payroll_impact_previews WHERE payroll_run_id = rec.id) THEN
            RAISE NOTICE 'Skipping % - preview exists', rec.name;
            CONTINUE;
        END IF;
        
        -- Find the previous payroll run for the same entity
        SELECT id, 
               COALESCE(total_gross_pay, 0),
               COALESCE(total_net_pay, 0),
               COALESCE(total_paye, 0),
               COALESCE(total_pension_employer, 0) + COALESCE(total_gross_pay, 0) + COALESCE(total_nsitf, 0) + COALESCE(total_itf, 0),
               COALESCE(total_employees, 0)
        INTO prev_id, prev_gross, prev_net, prev_paye, prev_emp_cost, prev_emp_count
        FROM payroll_runs
        WHERE entity_id = rec.entity_id
          AND id != rec.id
          AND status IN ('APPROVED', 'PROCESSING', 'COMPLETED', 'PAID')
          AND period_end < rec.period_start
        ORDER BY period_end DESC
        LIMIT 1;
        
        -- Set defaults if no previous payroll
        IF prev_id IS NULL THEN
            prev_gross := 0;
            prev_net := 0;
            prev_paye := 0;
            prev_emp_cost := 0;
            prev_emp_count := 0;
        END IF;
        
        -- Calculate current employer cost
        curr_emp_cost := rec.total_gross_pay + rec.total_pension_employer + rec.total_nsitf + rec.total_itf;
        
        -- Calculate variances
        g_variance := rec.total_gross_pay - prev_gross;
        n_variance := rec.total_net_pay - prev_net;
        p_variance := rec.total_paye - prev_paye;
        e_variance := curr_emp_cost - prev_emp_cost;
        
        -- Calculate variance percentage
        IF prev_gross > 0 THEN
            g_variance_pct := ROUND((g_variance / prev_gross) * 100, 2);
        ELSIF rec.total_gross_pay > 0 THEN
            g_variance_pct := 100.00;
        ELSE
            g_variance_pct := 0.00;
        END IF;
        
        -- Ensure variance percent is within bounds
        IF g_variance_pct > 999.99 THEN
            g_variance_pct := 999.99;
        ELSIF g_variance_pct < -999.99 THEN
            g_variance_pct := -999.99;
        END IF;
        
        -- Generate summary
        summary := 'Payroll for ' || TO_CHAR(rec.period_start, 'Month YYYY') || '. ' ||
                   'Total gross: ₦' || TO_CHAR(rec.total_gross_pay, 'FM999,999,999.00') || '. ' ||
                   'Employees: ' || rec.total_employees || '.';
        
        -- Insert impact preview
        INSERT INTO payroll_impact_previews (
            id,
            payroll_run_id,
            previous_payroll_id,
            current_gross,
            current_net,
            current_paye,
            current_employer_cost,
            current_employee_count,
            previous_gross,
            previous_net,
            previous_paye,
            previous_employer_cost,
            previous_employee_count,
            gross_variance,
            gross_variance_percent,
            net_variance,
            paye_variance,
            employer_cost_variance,
            variance_drivers,
            new_hires_count,
            new_hires_cost,
            terminations_count,
            terminations_savings,
            impact_summary,
            generated_at,
            created_at,
            updated_at
        ) VALUES (
            gen_random_uuid(),
            rec.id,
            prev_id,
            rec.total_gross_pay,
            rec.total_net_pay,
            rec.total_paye,
            curr_emp_cost,
            rec.total_employees,
            prev_gross,
            prev_net,
            prev_paye,
            prev_emp_cost,
            prev_emp_count,
            g_variance,
            g_variance_pct,
            n_variance,
            p_variance,
            e_variance,
            '[]'::jsonb,
            0,
            0,
            0,
            0,
            summary,
            NOW(),
            NOW(),
            NOW()
        );
        
        RAISE NOTICE 'Created preview for: %', rec.name;
    END LOOP;
END $$;

-- Verify the results
SELECT COUNT(*) as total_previews FROM payroll_impact_previews;

SELECT pip.id, pr.name, pip.current_gross, pip.gross_variance_percent, pip.current_employee_count
FROM payroll_impact_previews pip
JOIN payroll_runs pr ON pip.payroll_run_id = pr.id
ORDER BY pr.period_start
LIMIT 15;
