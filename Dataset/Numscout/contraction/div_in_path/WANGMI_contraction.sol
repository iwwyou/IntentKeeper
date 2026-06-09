pragma solidity ^0.6.12;

interface IUniswapV2Router01 {
    function factory() external pure returns (address);
    function WETH() external pure returns (address);

    function addLiquidity(
        address tokenA,
        address tokenB,
        uint amountADesired,
        uint amountBDesired,
        uint amountAMin,
        uint amountBMin,
        address to,
        uint deadline
    ) external returns (uint amountA, uint amountB, uint liquidity);
    function addLiquidityETH(
        address token,
        uint amountTokenDesired,
        uint amountTokenMin,
        uint amountETHMin,
        address to,
        uint deadline
    ) external payable returns (uint amountToken, uint amountETH, uint liquidity);
    function removeLiquidity(
        address tokenA,
        address tokenB,
        uint liquidity,
        uint amountAMin,
        uint amountBMin,
        address to,
        uint deadline
    ) external returns (uint amountA, uint amountB);
    function removeLiquidityETH(
        address token,
        uint liquidity,
        uint amountTokenMin,
        uint amountETHMin,
        address to,
        uint deadline
    ) external returns (uint amountToken, uint amountETH);
    function removeLiquidityWithPermit(
        address tokenA,
        address tokenB,
        uint liquidity,
        uint amountAMin,
        uint amountBMin,
        address to,
        uint deadline,
        bool approveMax, uint8 v, bytes32 r, bytes32 s
    ) external returns (uint amountA, uint amountB);
    function removeLiquidityETHWithPermit(
        address token,
        uint liquidity,
        uint amountTokenMin,
        uint amountETHMin,
        address to,
        uint deadline,
        bool approveMax, uint8 v, bytes32 r, bytes32 s
    ) external returns (uint amountToken, uint amountETH);
    function swapExactTokensForTokens(
        uint amountIn,
        uint amountOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) external returns (uint[] memory amounts);
    function swapTokensForExactTokens(
        uint amountOut,
        uint amountInMax,
        address[] calldata path,
        address to,
        uint deadline
    ) external returns (uint[] memory amounts);
    function swapExactETHForTokens(uint amountOutMin, address[] calldata path, address to, uint deadline)
        external
        payable
        returns (uint[] memory amounts);
    function swapTokensForExactETH(uint amountOut, uint amountInMax, address[] calldata path, address to, uint deadline)
        external
        returns (uint[] memory amounts);
    function swapExactTokensForETH(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline)
        external
        returns (uint[] memory amounts);
    function swapETHForExactTokens(uint amountOut, address[] calldata path, address to, uint deadline)
        external
        payable
        returns (uint[] memory amounts);

    function quote(uint amountA, uint reserveA, uint reserveB) external pure returns (uint amountB);
    function getAmountOut(uint amountIn, uint reserveIn, uint reserveOut) external pure returns (uint amountOut);
    function getAmountIn(uint amountOut, uint reserveIn, uint reserveOut) external pure returns (uint amountIn);
    function getAmountsOut(uint amountIn, address[] calldata path) external view returns (uint[] memory amounts);
    function getAmountsIn(uint amountOut, address[] calldata path) external view returns (uint[] memory amounts);
}

interface IUniswapV2Router02 is IUniswapV2Router01 {
    function removeLiquidityETHSupportingFeeOnTransferTokens(
        address token,
        uint liquidity,
        uint amountTokenMin,
        uint amountETHMin,
        address to,
        uint deadline
    ) external returns (uint amountETH);
    function removeLiquidityETHWithPermitSupportingFeeOnTransferTokens(
        address token,
        uint liquidity,
        uint amountTokenMin,
        uint amountETHMin,
        address to,
        uint deadline,
        bool approveMax, uint8 v, bytes32 r, bytes32 s
    ) external returns (uint amountETH);

    function swapExactTokensForTokensSupportingFeeOnTransferTokens(
        uint amountIn,
        uint amountOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) external;
    function swapExactETHForTokensSupportingFeeOnTransferTokens(
        uint amountOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) external payable;
    function swapExactTokensForETHSupportingFeeOnTransferTokens(
        uint amountIn,
        uint amountOutMin,
        address[] calldata path,
        address to,
        uint deadline
    ) external;
}

abstract contract Context {
    function _msgSender() internal view virtual returns (address) {
        return msg.sender;
    }

    function _msgData() internal view virtual returns (bytes calldata) {
        this; 
        return msg.data;
    }
}

contract Ownable is Context {
    address private _owner;

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    constructor () public {
        address msgSender = _msgSender();
        _owner = msgSender;
        emit OwnershipTransferred(address(0), msgSender);
    }

    
    function owner() public view returns (address) {
        return _owner;
    }
    
    modifier onlyOwner() {
        require(_owner == _msgSender(), "Ownable: caller is not the owner");
        _;
    }
    
    function renounceOwnership() public virtual onlyOwner {
        emit OwnershipTransferred(_owner, address(0));
        _owner = address(0);
    }
    
    function transferOwnership(address newOwner) public virtual onlyOwner {
        require(newOwner != address(0), "Ownable: new owner is the zero address");
        emit OwnershipTransferred(_owner, newOwner);
        _owner = newOwner;
    }
}

contract ERC20 is Context {
    using SafeMath for uint256;

    mapping(address => uint256) private _balances;

    mapping(address => mapping(address => uint256)) private _allowances;

    uint256 private _totalSupply;

    string private _name;
    string private _symbol;

    constructor(string memory name_, string memory symbol_) public {
        _name = name_;
        _symbol = symbol_;
    }
    
    function name() public view virtual override returns (string memory) {
        return _name;
    }
  
    function symbol() public view virtual override returns (string memory) {
        return _symbol;
    }
   
    function decimals() public view virtual override returns (uint8) {
        return 9;
    }
   
    function totalSupply() public view virtual override returns (uint256) {
        return _totalSupply;
    }
    
    function balanceOf(address account) public view virtual override returns (uint256) {
        return _balances[account];
    }

    function _beforeTokenTransfer(
        address _from,
        address to,
        uint256 amount
    ) internal virtual {}

    function _transfer(
        address sender,
        address recipient,
        uint256 amount
    ) internal virtual {
        require(sender != address(0), "ERC20: transfer _from the zero address");
        require(recipient != address(0), "ERC20: transfer to the zero address");

        _beforeTokenTransfer(sender, recipient, amount);

        _balances[sender] = _balances[sender].sub(amount, "ERC20: transfer amount exceeds balance");
        _balances[recipient] = _balances[recipient].add(amount);
        emit Transfer(sender, recipient, amount);
    }

    function _approve(
        address owner,
        address spender,
        uint256 amount
    ) internal virtual {
        require(owner != address(0), "ERC20: approve _from the zero address");
        require(spender != address(0), "ERC20: approve to the zero address");

        _allowances[owner][spender] = amount;
        emit Approval(owner, spender, amount);
    }
   
    function transfer(address recipient, uint256 amount) public virtual override returns (bool) {
        _transfer(_msgSender(), recipient, amount);
        return true;
    }
    
    function allowance(address owner, address spender) public view virtual override returns (uint256) {
        return _allowances[owner][spender];
    }
    
    function approve(address spender, uint256 amount) public virtual override returns (bool) {
        _approve(_msgSender(), spender, amount);
        return true;
    }
   
    function transferFrom(
        address sender,
        address recipient,
        uint256 amount
    ) public virtual override returns (bool) {
        _transfer(sender, recipient, amount);
        _approve(sender, _msgSender(), _allowances[sender][_msgSender()].sub(amount, "ERC20: transfer amount exceeds allowance"));
        return true;
    }
    
    function increaseAllowance(address spender, uint256 addedValue) public virtual returns (bool) {
        _approve(_msgSender(), spender, _allowances[_msgSender()][spender].add(addedValue));
        return true;
    }
    
    function decreaseAllowance(address spender, uint256 subtractedValue) public virtual returns (bool) {
        _approve(_msgSender(), spender, _allowances[_msgSender()][spender].sub(subtractedValue, "ERC20: decreased allowance below zero"));
        return true;
    }        
   
    function _mint(address account, uint256 amount) internal virtual {
        require(account != address(0), "ERC20: mint to the zero address");

        _beforeTokenTransfer(address(0), account, amount);

        _totalSupply = _totalSupply.add(amount);
        _balances[account] = _balances[account].add(amount);
        emit Transfer(address(0), account, amount);
    }

    function _burn(address account, uint256 amount) internal virtual {
        require(account != address(0), "ERC20: burn from the zero address");

        _beforeTokenTransfer(account, address(0), amount);

        _balances[account] = _balances[account].sub(amount, "ERC20: burn amount exceeds balance");
        _totalSupply = _totalSupply.sub(amount);
        emit Transfer(account, address(0), amount);
    }         
}

contract WANGMI is ERC20, Ownable {
    using SafeMath for uint256;

    IUniswapV2Router02 public constant uniswapV2Router = IUniswapV2Router02(0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D);
    uint256 public buyLiquidityFee = 3;
    uint256 public sellLiquidityFee = 3;
    uint256 public buyTxFee = 9;
    uint256 public sellTxFee = 9;
    uint256 public tokensForLiquidity;
    uint256 public tokensForTax;
    uint256 public _tTotal = 10**9 * 10**9;                         
    uint256 public swapAtAmount = _tTotal.mul(10).div(10000);  
    uint256 public maxTxLimit = _tTotal.mul(75).div(10000); 
    uint256 public maxWalletLimit = _tTotal.mul(150).div(10000);
    address public dev;
    address public deployer;
    address public uniswapV2Pair;
    uint256 private launchBlock;
    bool private swapping;
    bool public isLaunched;
    mapping (address => bool) public isExcludedFromFees;
    mapping (address => bool) public isExcludedFromTxLimit;
    mapping (address => bool) public isExcludedFromWalletLimit;
    mapping (address => bool) public isBlacklisted;

    function _swapTokensForETH(uint256 tokenAmount) private {

        address[] memory path = new address[](2);
        path[0] = address(this);
        path[1] = uniswapV2Router.WETH();

        uniswapV2Router.swapExactTokensForETHSupportingFeeOnTransferTokens(
            tokenAmount,
            0,
            path,
            address(this),
            block.timestamp
        );
    }

    function _addLiquidity(uint256 tokenAmount, uint256 ethAmount) private {

        uniswapV2Router.addLiquidityETH{value: ethAmount}(
            address(this),
            tokenAmount,
            0,
            0,
            deployer,
            block.timestamp
        );
    }

    function swapBack(uint256 totalTokensForFee) private {
        uint256 toSwap = swapAtAmount;
   
        uint256 liquidityTokens = toSwap.mul(tokensForLiquidity).div(totalTokensForFee).div(2);
        uint256 taxTokens = toSwap.sub(liquidityTokens).sub(liquidityTokens);
        uint256 amountToSwapForETH = toSwap.sub(liquidityTokens);

        _swapTokensForETH(amountToSwapForETH);

        uint256 ethBalance = address(this).balance;
        uint256 ethForTax = ethBalance.mul(taxTokens).div(amountToSwapForETH);
        uint256 ethForLiquidity = ethBalance.sub(ethForTax);

        tokensForLiquidity = tokensForLiquidity.sub(liquidityTokens.mul(2));
        tokensForTax = tokensForTax.sub(toSwap.sub(liquidityTokens.mul(2)));

        payable(address(dev)).transfer(ethForTax);
        _addLiquidity(liquidityTokens, ethForLiquidity);
    }    

    function _setBlacklist(address account, bool value) internal {
        isBlacklisted[account] = value;
    }

    function _transfer(address _from, address to, uint256 amount) internal override {
        require(_from != address(0), "transfer from the zero address");
        require(to != address(0), "transfer to the zero address");
        require(amount <= maxTxLimit || isExcludedFromTxLimit[_from] || isExcludedFromTxLimit[to], "Tx Amount too large");
        require(balanceOf(to).add(amount) <= maxWalletLimit || isExcludedFromWalletLimit[to], "Transfer will exceed wallet limit");
        require(isLaunched || isExcludedFromFees[_from] || isExcludedFromFees[to], "Waiting to go live");
        require(!isBlacklisted[_from], "Sender is blacklisted");

        if(amount == 0) {
            super._transfer(_from, to, 0);
            return;
        }

        uint256 totalTokensForFee = tokensForLiquidity + tokensForTax;
        bool canSwap = totalTokensForFee >= swapAtAmount;

        if(
            _from != uniswapV2Pair &&
            canSwap &&
            !swapping
        ) {
            swapping = true;
            swapBack(totalTokensForFee);
            swapping = false;
        } else if(
            _from == uniswapV2Pair &&
            to != uniswapV2Pair &&
            block.number < launchBlock + 2 &&
            !isExcludedFromFees[to]
        ) {
            _setBlacklist(to, true);
        }

        bool takeFee = !swapping;

        if(isExcludedFromFees[_from] || isExcludedFromFees[to]) {
            takeFee = false;
        }

        if(takeFee) {
            uint256 fees;
           
            if (to == uniswapV2Pair) {
                uint256 sellTotalFees = sellLiquidityFee.add(sellTxFee);
                fees = amount.mul(sellTotalFees).div(100);
                tokensForLiquidity = tokensForLiquidity.add(fees.mul(sellLiquidityFee).div(sellTotalFees));
                tokensForTax = tokensForTax.add(fees.mul(sellTxFee).div(sellTotalFees));
            }          
            else {
                uint256 buyTotalFees = buyLiquidityFee.add(buyTxFee);
                fees = amount.mul(buyTotalFees).div(100);
                tokensForLiquidity = tokensForLiquidity.add(fees.mul(buyLiquidityFee).div(buyTotalFees));
                tokensForTax = tokensForTax.add(fees.mul(buyTxFee).div(buyTotalFees));
            }

            if(fees > 0){
                super._transfer(_from, address(this), fees);
                amount = amount.sub(fees);
            }
        }

        super._transfer(_from, to, amount);
    }
}