pragma solidity ^0.8.4;
pragma abicoder v1;

contract UToken is Controller, ReentrancyGuardUpgradeable {
    using SafeERC20Upgradeable for IUErc20;

    bool public constant IS_UTOKEN = true;
    uint256 public constant WAD = 1e18;
    uint256 internal constant BORROW_RATE_MAX_MANTISSA = 0.0005e16;
    uint256 internal constant RESERVE_FACTORY_MAX_MANTISSA = 1e18;

    address public underlying;
    IInterestRateModel public interestRateModel;
    uint256 internal initialExchangeRateMantissa;
    uint256 public reserveFactorMantissa;
    uint256 public accrualBlockNumber;
    uint256 public borrowIndex;
    uint256 public totalBorrows;
    uint256 public totalReserves;
    uint256 public totalRedeemable;
    uint256 public overdueBlocks;
    uint256 public originationFee;
    uint256 public debtCeiling;
    uint256 public maxBorrow;
    uint256 public minBorrow;
    address public assetManager;
    address public userManager;
    IUErc20 public uErc20;

    struct BorrowSnapshot {
        uint256 principal;
        uint256 interest;
        uint256 interestIndex;
        uint256 lastRepay;
    }

    mapping(address => BorrowSnapshot) internal accountBorrows;

    event LogBorrow(address indexed account, uint256 amount, uint256 fee);

    modifier onlyMember(address account) {
        require(IUserManager(userManager).checkIsMember(account), "UToken: caller is not a member");
        _;
    }

    function getRemainingLoanSize() public view returns (uint256) {
        if (debtCeiling >= totalBorrows) {
            return debtCeiling - totalBorrows;
        } else {
            return 0;
        }
    }

    function getLastRepay(address account) public view returns (uint256 lastRepay) {
        lastRepay = accountBorrows[account].lastRepay;
    }

    function checkIsOverdue(address account) public view returns (bool isOverdue) {
        if (getBorrowed(account) == 0) {
            isOverdue = false;
        } else {
            uint256 lastRepay = getLastRepay(account);
            uint256 diff = getBlockNumber() - lastRepay;
            isOverdue = (overdueBlocks < diff);
        }
    }

    function calculatingFee(uint256 amount) public view returns (uint256) {
        return (originationFee * amount) / WAD;
    }

    function getBorrowed(address account) public view returns (uint256 borrowed) {
        borrowed = accountBorrows[account].principal;
    }

    function borrowBalanceView(address account) public view returns (uint256) {
        return accountBorrows[account].principal + calculatingInterest(account);
    }

    function borrowBalanceStoredInternal(address account) internal view returns (uint256) {
        BorrowSnapshot memory loan = accountBorrows[account];

        if (loan.principal == 0) {
            return 0;
        }

        uint256 principalTimesIndex = (loan.principal + loan.interest) * borrowIndex;
        return principalTimesIndex / loan.interestIndex;
    }

    function borrowRatePerBlock() public view returns (uint256) {
        uint256 borrowRateMantissa = interestRateModel.getBorrowRate();
        require(borrowRateMantissa <= BORROW_RATE_MAX_MANTISSA, "borrow rate is absurdly high");
        return borrowRateMantissa;
    }

    function calculatingInterest(address account) public view returns (uint256) {
        BorrowSnapshot memory loan = accountBorrows[account];

        if (loan.principal == 0) {
            return 0;
        }

        uint256 borrowRate = borrowRatePerBlock();
        uint256 currentBlockNumber = getBlockNumber();
        uint256 blockDelta = currentBlockNumber - accrualBlockNumber;
        uint256 simpleInterestFactor = borrowRate * blockDelta;
        uint256 borrowIndexNew = (simpleInterestFactor * borrowIndex) / WAD + borrowIndex;

        uint256 principalTimesIndex = (loan.principal + loan.interest) * borrowIndexNew;
        uint256 balance = principalTimesIndex / loan.interestIndex;

        return balance - accountBorrows[account].principal;
    }

    function borrow(uint256 amount) external onlyMember(msg.sender) whenNotPaused nonReentrant {
        IAssetManager assetManagerContract = IAssetManager(assetManager);
        require(amount >= minBorrow, "UToken: amount less than loan size min");

        require(amount <= getRemainingLoanSize(), "UToken: amount more than loan global size max");

        uint256 fee = calculatingFee(amount);
        require(borrowBalanceView(msg.sender) + amount + fee <= maxBorrow, "UToken: amount large than borrow size max");

        require(!checkIsOverdue(msg.sender), "UToken: Member has loans overdue");

        require(amount <= assetManagerContract.getLoanableAmount(underlying), "UToken: Not enough to lend out");
        require(uint256(_getCreditLimit(msg.sender)) >= amount + fee, "UToken: The loan amount plus fee is greater than credit limit");

        require(accrueInterest(), "UToken: accrue interest failed");

        uint256 borrowedAmount = borrowBalanceStoredInternal(msg.sender);

        if (accountBorrows[msg.sender].lastRepay == 0) {
            accountBorrows[msg.sender].lastRepay = getBlockNumber();
        }

        uint256 accountBorrowsNew = borrowedAmount + amount + fee;
        uint256 totalBorrowsNew = totalBorrows + amount + fee;
        uint256 oldPrincipal = accountBorrows[msg.sender].principal;

        accountBorrows[msg.sender].principal += amount + fee;
        uint256 newPrincipal = accountBorrows[msg.sender].principal;
        IUserManager(userManager).updateLockedData(msg.sender, newPrincipal - oldPrincipal, true);
        accountBorrows[msg.sender].interest = accountBorrowsNew - accountBorrows[msg.sender].principal;
        accountBorrows[msg.sender].interestIndex = borrowIndex;
        totalBorrows = totalBorrowsNew;
        totalReserves += fee;

        require(assetManagerContract.withdraw(underlying, msg.sender, amount), "UToken: Failed to withdraw");

        emit LogBorrow(msg.sender, amount, fee);
    }

    function accrueInterest() public returns (bool) {
        uint256 borrowRate = borrowRatePerBlock();
        uint256 currentBlockNumber = getBlockNumber();
        uint256 blockDelta = currentBlockNumber - accrualBlockNumber;

        uint256 simpleInterestFactor = borrowRate * blockDelta;
        uint256 interestAccumulated = (simpleInterestFactor * totalBorrows) / WAD;
        uint256 totalBorrowsNew = interestAccumulated + totalBorrows;
        uint256 borrowIndexNew = (simpleInterestFactor * borrowIndex) / WAD + borrowIndex;

        accrualBlockNumber = currentBlockNumber;
        borrowIndex = borrowIndexNew;
        totalBorrows = totalBorrowsNew;

        return true;
    }

    function getBlockNumber() internal view returns (uint256) {
        return block.number;
    }

    function _getCreditLimit(address account) private view returns (int256) {
        return IUserManager(userManager).getCreditLimit(account);
    }
}
