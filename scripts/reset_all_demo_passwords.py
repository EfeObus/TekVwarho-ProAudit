#!/usr/bin/env python3
"""
Reset all demo account passwords in the Railway database.
"""

import psycopg2
from passlib.context import CryptContext

DATABASE_URL = 'postgresql://postgres:eKFYCXhJUxqIFcXQjZnLmZlQBBNEbsNy@turntable.proxy.rlwy.net:28165/railway'

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto', bcrypt__truncate_error=False)

def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # List of demo accounts to reset with their passwords
    demo_accounts = [
        ('superadmin@tekvwarho.com', 'SuperAdmin@TekVwarho2026!'),
        ('test.admin@tekvwarho.com', 'TestAdmin@2026!'),
        ('it.dev@tekvwarho.com', 'ItDev@2026!'),
        ('support@tekvwarho.com', 'Support@2026!'),
        ('efeobukohwo64@gmail.com', 'Efeobus12345'),
        ('admin@okonkwotrading.com', 'Okonkwo2024!'),
        ('admin@lagosprime.com', 'LagosPrime2024!'),
    ]
    
    print('=' * 60)
    print('Resetting Demo Account Passwords')
    print('=' * 60)
    
    for email, password in demo_accounts:
        new_hash = hash_password(password)
        cursor.execute(
            'UPDATE users SET hashed_password = %s WHERE email = %s RETURNING email',
            (new_hash, email)
        )
        result = cursor.fetchone()
        if result:
            print(f'  ✅ {email}')
        else:
            print(f'  ❌ {email} (not found)')
    
    # Reset all org user passwords to a standard password
    staff_password = 'Staff2024!'
    staff_hash = hash_password(staff_password)
    
    print('\n' + '-' * 60)
    print('Resetting Staff Account Passwords')
    print('-' * 60)
    
    cursor.execute("""
        SELECT email FROM users 
        WHERE (email LIKE '%@okonkwotrading.com' 
           OR email LIKE '%@lagosprime.com'
           OR email LIKE '%@efeobusfurniture.com.ng')
        AND email NOT IN ('admin@okonkwotrading.com', 'admin@lagosprime.com')
    """)
    staff_emails = cursor.fetchall()
    
    for (email,) in staff_emails:
        cursor.execute(
            'UPDATE users SET hashed_password = %s WHERE email = %s',
            (staff_hash, email)
        )
        print(f'  ✅ {email} -> Staff2024!')
    
    conn.commit()
    print('\n' + '=' * 60)
    print('✅ All passwords reset successfully!')
    print('=' * 60)
    
    # Print login credentials
    print('\n📋 LOGIN CREDENTIALS:')
    print('-' * 60)
    print('Platform Staff:')
    print('  superadmin@tekvwarho.com / SuperAdmin@TekVwarho2026!')
    print('  test.admin@tekvwarho.com / TestAdmin@2026!')
    print('  it.dev@tekvwarho.com / ItDev@2026!')
    print('  support@tekvwarho.com / Support@2026!')
    print('\nOrganization Owners:')
    print('  efeobukohwo64@gmail.com / Efeobus12345')
    print('  admin@okonkwotrading.com / Okonkwo2024!')
    print('  admin@lagosprime.com / LagosPrime2024!')
    print('\nStaff Accounts:')
    print('  All @okonkwotrading.com, @lagosprime.com, @efeobusfurniture.com.ng')
    print('  Password: Staff2024!')
    print('-' * 60)
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
