<?php
/* @var $filterPosition string */
/* @var $showCats bool */
/* @var $showSorting bool */
/* @var $sortingUrl string */
/* @var $sortingFuncList mixed */
/* @var $sorting string */
/* @var $showViewSwitch bool */
/* @var $thumbViewUrl string */
/* @var $tableViewUrl string */
/* @var $tableView bool */
?>
<?php if( $showSorting ) { ?>
	<div class="dropdown wb-store-list-controls-sort"
		 title="<?php echo htmlspecialchars($this->__('Sort')); ?>">
		<button type="button" id="store_sorter_dp"
				class="btn btn-default btn-sm dropdown-toggle"
				data-toggle="dropdown" aria-haspopup="true" aria-expanded="true">
			<?php echo ((isset($sortingFuncList[$sorting]) && $sortingFuncList[$sorting]->method) ? $sortingFuncList[$sorting]->name : $this->__('Sort')); ?>
			<span class="caret"></span>
		</button>
		<ul class="dropdown-menu <?php echo (empty($showCats) || $filterPosition != "top") ? 'dropdown-menu-left' : 'dropdown-menu-right'; ?>" aria-labelledby="store_sorter_dp">
			<?php foreach ($sortingFuncList as $k => $v): ?>
			<li<?php if ($k == $sorting) echo ' class="active"'; ?>>
				<a href="<?php echo htmlspecialchars(str_replace('__SORT__', $k, $sortingUrl)); ?>"><?php echo $this->__($v->name); ?></a>
			</li>
			<?php endforeach; ?>
		</ul>
	</div>
<?php } ?>
<?php if( $showViewSwitch ) { ?>
	<div class="wb-store-list-controls-view-switch">
		<a href="<?php echo htmlspecialchars($thumbViewUrl); ?>"
		   class="btn btn-default btn-sm<?php if (!$tableView) echo ' active'; ?>">
			<span class="glyphicon glyphicon-th"></span>
		</a>
		<a href="<?php echo htmlspecialchars($tableViewUrl); ?>"
		   class="btn btn-default btn-sm<?php if ($tableView) echo ' active'; ?>">
			<span class="glyphicon glyphicon-list"></span>
		</a>
	</div>
<?php } ?>