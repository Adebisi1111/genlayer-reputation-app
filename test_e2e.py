from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # Inject mock MetaMask BEFORE page scripts run
    page.add_init_script("""
        window.ethereum = {
            isMetaMask: true,
            request: async ({ method, params }) => {
                if (method === 'eth_requestAccounts' || method === 'eth_accounts') 
                    return ['0x70997970C51812dc3A010C7d01b50e0d17dc79C8'];
                if (method === 'eth_chainId') return '0x1085';
                if (method === 'wallet_switchEthereumChain') return null;
                if (method === 'wallet_addEthereumChain') return null;
                if (method === 'eth_getBalance') return '0x1bc16d674ec80000';
                if (method === 'wallet_getSnaps') return {};
                if (method === 'wallet_requestSnaps') return {};
                return '0x0';
            },
            on: () => {},
            removeListener: () => {},
        };
    """)
    
    page.goto('https://adebisi1111.github.io/genlayer-reputation-app/', wait_until='networkidle')
    time.sleep(2)
    
    # Take screenshot to see what's happening
    page.screenshot(path='/tmp/page_screenshot.png')
    
    # Test 1: Page loads
    title = page.title()
    print(f"TITLE: {title}")
    
    # Check if buttons exist
    buttons = page.locator('button')
    print(f"BUTTONS FOUND: {buttons.count()}")
    for i in range(buttons.count()):
        print(f"  BUTTON {i}: {buttons.nth(i).text_content()}")
    
    # Test 2: Connect wallet
    connectBtn = page.locator('#connectBtn')
    if connectBtn.count() > 0:
        connectBtn.click()
        time.sleep(1)
        addr = page.locator('#addr').text_content()
        print(f"AFTER CONNECT: {addr}")
    
    browser.close()
    print("TEST COMPLETE")
