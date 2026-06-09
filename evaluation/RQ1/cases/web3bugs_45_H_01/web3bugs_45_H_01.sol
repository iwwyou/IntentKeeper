pragma solidity ^0.8.4;

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

    event LogNewMarketInterestRateModel(address oldInterestRateModel, address newInterestRateModel);

    event LogMint(address minter, uint256 underlyingAmount, uint256 uTokenAmount);

    event LogRedeem(address redeemer, uint256 redeemTokensIn, uint256 redeemAmountIn, uint256 redeemAmount);

    event LogReservesAdded(address reserver, uint256 actualAddAmount, uint256 totalReservesNew);

    event LogReservesReduced(address receiver, uint256 reduceAmount, uint256 totalReservesNew);

    event LogBorrow(address indexed account, uint256 amount, uint256 fee);

    event LogRepay(address indexed account, uint256 amount);

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

    function calculatingFee(uint256 amount) public view returns (uint256) {
        return (originationFee * amount) / WAD;
    }

    function borrowRatePerBlock() public view returns (uint256) {
        uint256 borrowRateMantissa = interestRateModel.getBorrowRate();
        require(borrowRateMantissa <= BORROW_RATE_MAX_MANTISSA, "borrow rate is absurdly high");
        return borrowRateMantissa;
    }

    function getBlockNumber() internal view returns (uint256) {
        return block.number;
    }

    function getLastRepay(address account) public view returns (uint256 lastRepay) {
        lastRepay = accountBorrows[account].lastRepay;
    }

    function _getCreditLimit(address account) private view returns (int256) {
        return IUserManager(userManager).getCreditLimit(account);
    }

    function borrowBalanceStoredInternal(address account) internal view returns (uint256) {
        BorrowSnapshot memory loan = accountBorrows[account];

        if (loan.principal == 0) {
            return 0;
        }

        uint256 principalTimesIndex = (loan.principal + loan.interest) * borrowIndex;
        return principalTimesIndex / loan.interestIndex;
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

    function borrowBalanceView(address account) public view returns (uint256) {
        return accountBorrows[account].principal + calculatingInterest(account);
    }

    function getInterestIndex(address account) public view returns (uint256 interestIndex) {
        interestIndex = accountBorrows[account].interestIndex;
    }

    function getLoan(address member)
        public
        view
        returns (
            uint256 principal,
            uint256 totalBorrowed,
            address asset,
            uint256 apr,
            int256 limit,
            bool isOverdue,
            uint256 lastRepay
        )
    {
        principal = accountBorrows[msg.sender].principal;
        totalBorrowed = borrowBalanceStoredInternal(member);
        asset = underlying;
        apr = borrowRatePerBlock();
        lastRepay = getLastRepay(member);
        limit = _getCreditLimit(member);
        isOverdue = checkIsOverdue(member);
    }

    function getBorrowed(address account) public view returns (uint256 borrowed) {
        borrowed = accountBorrows[account].principal;
    }

    function supplyRatePerBlock() public view returns (uint256) {
        return interestRateModel.getSupplyRate(reserveFactorMantissa);
    }

    function exchangeRateStored() public view returns (uint256) {
        uint256 totalSupply_ = uErc20.totalSupply();
        if (totalSupply_ == 0) {
            return initialExchangeRateMantissa;
        } else {
            return (totalRedeemable * WAD) / totalSupply_;
        }
    }

    function exchangeRateCurrent() public nonReentrant returns (uint256) {
        require(accrueInterest(), "UToken: accrue interest failed");
        return exchangeRateStored();
    }

    function borrow(uint256 amount) external onlyMember(msg.sender) whenNotPaused nonReentrant {
        // @LocalVar amount = [1000000000000000001, 1000000000000000001]
        // @LocalVar account = symbolicAddress 101
        // @StateVar minBorrow = [2, 2]
        // @StateVar debtCeiling = [1000000000000000002, 1000000000000000002]
        // @StateVar totalBorrows = [0, 0]
        // @StateVar originationFee = [1000000000000001, 1000000000000001]
        // @StateVar WAD = [1000000000000000000, 1000000000000000000]
        // @StateVar accountBorrows[101].principal = [1000000000000000001, 1000000000000000001]
        // @StateVar accrualBlockNumber = [1, 1]
        // @StateVar borrowIndex = [1000000000000000001, 1000000000000000001]
        // @StateVar accountBorrows[101].interest = [1, 1]
        // @StateVar accountBorrows[101].interestIndex = [1000000000000000001, 1000000000000000001]
        // @StateVar accountBorrows[101].lastRepay = [1, 1]
        // @StateVar maxBorrow = [2001005000000000005, 2001005000000000005]
        // @StateVar overdueBlocks = [2, 2]
        // @GlobalVar block.number = [2, 2]
        IAssetManager assetManagerContract = IAssetManager(assetManager);
        require(amount >= minBorrow, "UToken: amount less than loan size min");

        require(amount <= getRemainingLoanSize(), "UToken: amount more than loan global size max");

        uint256 fee = calculatingFee(amount);
        // @During borrowIndex(Before < After)
        require(borrowBalanceView(msg.sender) + amount + fee <= maxBorrow, "UToken: amount large than borrow size max");

        // @During borrowIndex(Before < After)
        require(!checkIsOverdue(msg.sender), "UToken: Member has loans overdue");

        // @During borrowIndex(Before < After)
        require(amount <= assetManagerContract.getLoanableAmount(underlying), "UToken: Not enough to lend out");
        require(
            uint256(_getCreditLimit(msg.sender)) >= amount + fee,
            "UToken: The loan amount plus fee is greater than credit limit"
        );

        // @During borrowIndex(Before < After)
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
}
