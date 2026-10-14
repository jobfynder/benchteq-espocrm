define(['views/fields/link'], (LinkFieldView) => {
    // Lookup that offers only freelancers who passed screening (the Shortlist filter).
    return class extends LinkFieldView {
        setup() {
            super.setup();

            this.selectPrimaryFilterName = 'shortlist';
        }
    };
});
