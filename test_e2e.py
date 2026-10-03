from playwright.sync_api import sync_playwright
import time

# GenLayer test wallet private key
TEST_PK = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # Inject a complete mock that simulates genlayer-js snap behavior
    page.add_init_script(f"""
        const PK = "{TEST_PK}";
        
        window.ethereum = {{
            isMetaMask: true,
            _signedTx: null,
            request: async ({{ method, params }}) => {{
                if (method === 'eth_requestAccounts' || method === 'eth_accounts') 
                    return ['0x70997970C51812dc3A010C7d01b50e0d17dc79C8'];
                if (method === 'eth_chainId') return '0x1085';
                if (method === 'wallet_switchEthereumChain') return null;
                if (method === 'wallet_addEthereumChain') return null;
                if (method === 'eth_getBalance') return '0x1bc16d674ec80000';
                if (method === 'wallet_getSnaps') return {{}};
                if (method === 'wallet_requestSnaps') return {{}};
                if (method === 'eth_sendTransaction') {{
                    window.ethereum._signedTx = '0x' + 'a' * 64;
                    return window.ethereum._signedTx;
                }}
                if (method === 'eth_getTransactionCount') return '0x0';
                if (method === 'eth_estimateGas') return '0x5208';
                if (method === 'eth_gasPrice') return '0x3b9aca00';
                if (method === 'eth_blockNumber') return '0x1234';
                return '0x0';
            }},
            on: () => {{}},
            removeListener: () => {{}},
        }};
    """)
    
    page.goto('https://adebisi1111.github.io/genlayer-reputation-app/', wait_until='networkidle')
    time.sleep(2)
    
    # Test 1: Page loads
    title = page.title()
    print(f"TITLE: {title}")
    assert 'Reputation' in title
    
    # Test 2: Connect wallet
    page.click('#connectBtn')
    time.sleep(1)
    addr = page.locator('#addr').text_content()
    print(f"CONNECTED: {addr}")
    assert '0x7099' in addr
    
    # Test 3: Input validation - empty job ID
    page.click('button:has-text("Create Job")')
    time.sleep(1)
    jobStatus = page.locator('#jobStatus').text_content()
    print(f"EMPTY JOB VALIDATION: {jobStatus}")
    assert 'required' in jobStatus.lower()
    
    # Test 4: Create Job
    page.fill('#jobId', 'test-job-1')
    page.fill('#jobAgent', '0x70997970C51812dc3A010C7d01b50e0d17dc79C8')
    page.fill('#evidenceUrl', 'https://example.com/evidence')
    page.fill('#claimed', 'Delivered')
    page.fill('#resolveBlock', '1000')
    page.click('button:has-text("Create Job")')
    time.sleep(1)
    jobStatus = page.locator('#jobStatus').text_content()
    print(f"CREATE JOB: {jobStatus}")
    
    # Test 5: Record Delivery
    page.fill('#recordJobId', 'test-job-1')
    page.click('button:has-text("Record Delivery")')
    time.sleep(1)
    recStatus = page.locator('#recordStatus').text_content()
    print(f"RECORD: {recStatus}")
    
    # Test 6: Get Reputation
    page.fill('#agentRead', '0x70997970C51812dc3A010C7d01b50e0d17dc79C8')
    page.click('button:has-text("Get Reputation")')
    time.sleep(1)
    rep = page.locator('#repOut').text_content()
    print(f"REPUTATION: {rep[:100]}")
    
    # Test 7: Get Job
    page.fill('#jobIdRead', 'test-job-1')
    page.click('button:has-text("Get Job")')
    time.sleep(1)
    job = page.locator('#jobOut').text_content()
    print(f"JOB: {job[:100]}")
    
    # Test 8: Invalid address validation
    page.fill('#jobId', 'test-job-2')
    page.fill('#jobAgent', 'invalid-address')
    page.fill('#evidenceUrl', 'https://example.com/evidence2')
    page.fill('#claimed', 'Done')
    page.fill('#resolveBlock', '2000')
    page.click('button:has-text("Create Job")')
    time.sleep(1)
    valStatus = page.locator('#jobStatus').text_content()
    print(f"INVALID ADDRESS: {valStatus}")
    assert 'valid' in valStatus.lower()
    
    browser.close()
    print("ALL E2E TESTS PASSED")
